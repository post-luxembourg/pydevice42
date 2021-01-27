import json as js
import typing as t
from itertools import chain

import requests

from . import exceptions as d42exc
from . import types as tt
from .basicrestclient import BasicRestClient
from .logger import LOGGER


def extract_data(data: t.Dict[str, t.Any]) -> t.Any:
    """
    When using Device42's pagination functions the return json always
    looks like so:

    ```json
    {
        "limit": INT,
        "offset": INT,
        "thing_we_care_about": (...),
        "total_count": INT
    }
    ```

    This function simply returns the first non-meta field.
    """
    metadata_keys = ["offset", "total_count", "limit"]
    return data.get(next((k for k in data.keys() if k not in metadata_keys)))


class D42Client(BasicRestClient):
    def _check_err(self, jres: t.Any) -> tt.JSON_Res:
        """POST and PUT method validation

        Raises exception if the return code isn't 0.

        Else, returns the message from the server.
        This is _generally_ a t.List[t.Any], but I have generalised it to
        be any type of tt.JSON_Res
        """
        ret_code = int(jres["code"])
        ret_msg = jres.get("msg", [])
        if ret_code != 0:
            raise d42exc.ReturnCodeException(" ".join(map(str, ret_msg)))
        return ret_msg

    def _request(
        self,
        endpoint: str,
        params: t.Optional[t.Dict[str, t.Any]] = None,
        json: t.Optional[t.Dict[str, t.Any]] = None,
        data: t.Optional[t.Dict[str, t.Any]] = None,
        method: tt.HTTP_METHODS = "GET",
    ) -> tt.JSON_Res:
        res = self.request(
            url=endpoint, params=params, json=json, data=data, method=method
        )
        try:
            res.raise_for_status()
        except requests.HTTPError as err:
            if err.response.status_code == 500:
                try:
                    msg = err.response.json().get("msg", "")
                    if msg.startswith("License expired"):
                        raise d42exc.LicenseExpiredException(msg) from err
                    elif msg.startswith("License is not valid for"):
                        raise d42exc.LicenseInsufficientException(msg) from err
                except js.JSONDecodeError:
                    # Ignore JSON decode exception here. The backend may not
                    # talk JSON when returning 500's.
                    pass
            raise
        jres: tt.JSON_Res = res.json()
        if method in ["POST", "PUT"]:
            return self._check_err(jres)
        return jres

    def _paginated_request(
        self,
        endpoint: str,
        # FIXME Is there any paginated *non-* GET request?
        method: tt.HTTP_METHODS = "GET",
        params: t.Optional[t.Dict[str, t.Any]] = None,
        json: t.Optional[t.Dict[str, t.Any]] = None,
        data: t.Optional[t.Dict[str, t.Any]] = None,
        limit: int = 50,
    ) -> t.Iterable[tt.JSON_Res]:
        def page_request(new_params: t.Dict[str, t.Any]) -> tt.JSON_Dict:
            return t.cast(
                tt.JSON_Dict,
                self._request(
                    method=method,
                    endpoint=endpoint,
                    params=new_params,
                    data=data,
                    json=json,
                ),
            )

        request_num = 1

        params = {} if params is None else params
        params["limit"] = limit
        params["offset"] = 0

        # First request
        resp = page_request(params)
        # Process data
        resp_data: t.Any = extract_data(resp)
        if not resp_data:
            # Sometimes, we'll run a paginated _request
            # and just get back []
            # In these cases, we want to quickly StopIteration
            return resp_data

        total_count = tt.int_cast(resp.get("total_count"))

        yield resp_data

        processed = len(resp_data)

        while processed < total_count:
            params["offset"] += limit
            request_num += 1
            LOGGER.debug(
                f"Processing request #{request_num}) "
                f"[Offset: {params['offset']} - Limit: {limit}] "
                f"{len(resp_data)}/{total_count}"
            )
            resp = page_request(params)
            resp_data = extract_data(resp)
            processed += len(resp_data)
            yield resp_data

    def _flattened_paginated_request(
        self, *args: t.Any, **kwargs: t.Any
    ) -> t.Iterable[tt.JSON_Res]:
        return chain.from_iterable(
            t.cast(
                t.List[tt.JSON_Res], self._paginated_request(*args, **kwargs)
            )
        )

    def _get_object(
        self,
        endpoint: str,
        id: int,
        api_version: str = "1.0",
    ) -> t.Any:
        return self._request(endpoint=f"/api/{api_version}/{endpoint}/{id}")

    def _post_object(
        self,
        new_obj: t.Mapping[str, t.Any],
        endpoint: str,
        api_version: str = "1.0",
    ) -> tt.PostRes:
        """
        Generic POST.

        The only thing that we really care about is the `Mapping[str, Any]`.
        Strictly speaking, the mapping _should_ be:

        `Dict[str, JSON_VALUES]`
        where `JSON_Values = Union[str, int, float, bool, None]`

        But **of course**, mypy complains about
        [this](https://github.com/python/mypy/issues/4976).

        `TypedDicts` aren't an acceptable generic dict, because of invariance
        [nonsense](http://mypy.readthedocs.io/en/latest/common_issues.html#invariance-vs-covariance)
        and `JSON_VALUES` can't be mapped to our `TypedDicts`, because of
        `Literals`
        """

        return tt.PostRes(
            *self._request(
                endpoint=f"/api/{api_version}/{endpoint}/",
                method="POST",
                data=t.cast(t.Dict[str, t.Any], new_obj),
            )
        )

    def _put_object(
        self,
        new_obj: t.Mapping[str, t.Any],
        endpoint: str,
        api_version: str = "1.0",
    ) -> tt.PostRes:
        """
        Same as `_post_object` but uses the PUT method.
        The difference is that PUT is used exclusively for updating, whereas
        POST can be both update and create.
        """
        return tt.PostRes(
            *self._request(
                endpoint=f"/api/{api_version}/{endpoint}/",
                method="PUT",
                data=t.cast(t.Dict[str, t.Any], new_obj),
            )
        )

    def _delete_object(
        self, endpoint: str, id: int, api_version: str = "1.0"
    ) -> tt.DeleteRes:
        """
        Generic DELETE
        """
        return t.cast(
            tt.DeleteRes,
            self._request(
                endpoint=f"/api/{api_version}/{endpoint}/{id}",
                method="DELETE",
            ),
        )

    def get_DOQL_query(self, query_name: str) -> t.Any:
        """
        DOQL queries are custom usermade queries that talk directly to
        the database and (generally) return a JSON.

        They have to be coded by the user.
        """
        return self._request(
            method="GET",
            endpoint="/services/data/v1.0/query/",
            params={
                "saved_query_name": query_name,
                "delimiter": "",
                "header": "yes",
                "output_type": "json",
            },
        )

    def update_custom_field(
        self, cf: tt.CustomFieldBase, endpoint: str, api_version: str = "1.0"
    ) -> tt.JSON_Res:
        """
        Update a custom field for a given d42 object.

        Note that a CustomFieldBase's `value` is a string!

        This means that if you're inputting a json as a custom field
        you should cast it with `json.dumps`

        Example:

        ```python
        >>> client = D42Client(user, password, host)
        >>> client.update_custom_field(
        ...             {
        ...                 "id": 12,
        ...                 "key": "custom_data",
        ...                 "value": {
        ...                     "Testing": "I was sent from the API"
        ...                 },
        ...             },
        ...             "serviceinstance"
        ...         )
        Traceback (most recent call last):
        ...
        requests.exceptions.RequestException: <Response [500]>
        >>> client.update_custom_field(
        ...             {
        ...                 "id": 12,
        ...                 "key": "custom_data",
        ...                 "value": dumps({
        ...                     "Testing": "I was sent from the API"
        ...                 }),
        ...             },
        ...             "serviceinstance"
        ...         )
        (0, 'custom key pair values added or updated ...')
        ```
        """

        return self._request(
            method="PUT",
            endpoint=f"/api/{api_version}/custom_fields/{endpoint}/",
            data=t.cast(t.Dict[str, t.Any], cf),
        )

    ###########################################################################
    #                                BUILDINGS                                #
    ###########################################################################

    def get_buildings(self, name: t.Optional[str]) -> t.Iterable[tt.Building]:
        return self._flattened_paginated_request(
            endpoint="/api/1.0/buildings/", params={"name": name}
        )

    def post_building(self, building: tt.Building) -> tt.PostRes:
        return self._post_object(building, "buildings")

    def delete_building(self, id: int) -> tt.DeleteRes:
        return self._delete_object(endpoint="buildings", id=id)

    ###########################################################################
    #                                  ROOMS                                  #
    ###########################################################################

    def get_rooms(
        self,
        name: t.Optional[str],
        building_id: t.Optional[str],
        building: t.Optional[str],
    ) -> t.Iterable[tt.Room]:
        return self._flattened_paginated_request(
            endpoint="/api/1.0/rooms/",
            params={
                "name": name,
                "building_id": building_id,
                "building": building,
            },
        )

    def get_room(
        self,
        id: int,
    ) -> tt.Room:
        return t.cast(tt.Room, self._get_object(endpoint="rooms", id=id))

    def post_room(self, room: tt.Room) -> tt.PostRes:
        return self._post_object(room, "rooms")

    def delete_room(self, id: int) -> tt.DeleteRes:
        return self._delete_object(endpoint="rooms", id=id)

    ###########################################################################
    #                                  RACKS                                  #
    ###########################################################################

    def get_racks(self, **kwargs: tt.RackGet) -> t.Iterable[tt.Rack]:
        return self._flattened_paginated_request(
            endpoint="/api/1.0/racks/",
            params=kwargs,
        )

    def get_rack(
        self,
        id: int,
    ) -> tt.Rack:
        return t.cast(tt.Rack, self._get_object(endpoint="racks", id=id))

    def post_rack(self, rack: tt.Rack) -> tt.PostRes:
        return self._post_object(rack, "racks")

    def delete_rack(self, id: int) -> tt.DeleteRes:
        return self._delete_object(endpoint="racks", id=id)

    ###########################################################################
    #                                 DEVICES                                 #
    ###########################################################################

    def get_devices(self, **kwargs: tt.DeviceGet) -> t.Iterable[tt.Device]:
        return self._flattened_paginated_request(
            "/api/1.0/devices/", params=kwargs
        )

    def get_all_devices(
        self, include_cols: t.Optional[str] = None
    ) -> t.Iterable[tt.Device]:
        """
        Apparently, get _all_ devices is a little more detailed than just
        devices. Who knew.

        Anyway, `include_cols` will limit the columns you want to display.

        See the documentation for more info:
        [here](https://api.device42.com/#!/Devices/getDevicesAll)
        """
        return self._flattened_paginated_request(
            "/api/1.0/devices/all", params={"include_cols": include_cols}
        )

    def get_device(self, id: int, **kwargs: tt.DeviceGet) -> tt.Device:
        return t.cast(tt.Device, self._get_object(endpoint="devices", id=id))

    def get_device_by_other_id(
        self,
        id: int,
        type: t.Literal["customer", "name", "serial", "asset"],
        include_cols: str,
    ) -> t.Iterable[tt.Device]:
        """
        You can find devices associated with some other objects id trivially
        through this get
        """
        return self._flattened_paginated_request(
            endpoint=f"devices/{type}/{id}"
        )

    ###########################################################################
    #                                 OTHERS                                  #
    ###########################################################################

    def get_all_service_instances(self) -> t.Iterable[tt.JSON_Res]:
        return self._flattened_paginated_request("/api/2.0/service_instances/")

    def get_all_application_components(self) -> t.Iterable[tt.JSON_Res]:
        return self._flattened_paginated_request("/api/1.0/appcomps/")

    def get_all_operating_systems(self) -> t.Iterable[tt.JSON_Res]:
        return self._flattened_paginated_request("/api/1.0/operatingsystems/")

    def post_network(self, new_subnet: tt.Subnet) -> tt.JSON_Res:
        return self._post_object(new_subnet, "subnets")

    def post_ip(self, new_ip: tt.IPAddress) -> tt.JSON_Res:
        return self._post_object(new_ip, "ips")

    def post_app_component(
        self,
        new_component: tt.AppComponent,
    ) -> tt.JSON_Res:
        return self._post_object(new_component, "appcomps")

    def post_customer(self, new_customer: tt.Customer) -> tt.JSON_Res:
        return self._post_object(new_customer, "customers")
