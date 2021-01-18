import typing as t
from ipaddress import IPv4Address, IPv6Address

# Representing JSON is notoriously tricky in mypy
# Here's the best attempt I have so far
# A JSON_RES is either a list of JSON_DICTS, or just a straight up JSON_DICT
# JSON_LIST contains JSON_DICTS
# And a JSON_DICT is a simple map to acceptable JSON_VALUES
# So JSONS that contain JSONS are not acceptable, because MYPY can't represent
# self-referential values
# Meaning that if we get some sort of fancy value, we have to cast it
# to the appropriately typed dict
JSON_Values = t.Union[str, int, float, bool, None]

JSON_Dict = t.Dict[str, JSON_Values]

JSON_List = t.List[JSON_Dict]

JSON_Res = t.Any

HTTP_METHODS = t.Literal["GET", "POST", "PUT", "DELETE"]
STATUS = t.Literal["USED", "UNUSED"]
T = t.TypeVar("T")


class DeleteRes(t.TypedDict):
    """
    Response we get from Device42 whenever we attempt to delete na object
    """

    deleted: bool
    id: int


class PostRes(t.NamedTuple):
    """
    Base Response we get from Device42 whenever we attempt to post an object

    The message will contain either of the following strings:

    `<Name Of object> added or updated`
    or
    `<Name Of object> added/updated`

    The id is a simple int that signifies how the object is identified in the
    database, whereas the identifier is how _we_ identify the object.

    Some post methods (not all) include these two final booleans.
    """

    message: str
    id: int
    identifier: t.Any
    created: t.Optional[bool] = None
    updated: t.Optional[bool] = None


def int_cast(i: t.Any) -> int:
    return int(t.cast(t.SupportsInt, i))


class Vlan(t.TypedDict, total=False):
    number: str
    name: str
    description: str
    notes: str
    vlan_id: str


class SubnetBase(t.TypedDict):
    network: str
    mask_bits: str
    name: str


class Subnet(SubnetBase, total=False):
    description: str
    notes: str


class IPAddressBase(t.TypedDict):
    """
    Only real attribute we need is a valid ipaddress
    The request method then handles converting it into an
    str
    """

    ipaddress: t.Union[IPv4Address, IPv6Address]


class IPAddress(IPAddressBase, total=False):
    label: str
    subnet: str
    macaddress: str
    device: str
    type: t.Literal["static", "dhcp", "reserved"]
    vrf_group_id: str
    vrf_group: str
    available: t.Literal["yes", "no"]
    clear_all: t.Literal["yes", "no"]
    tags: str


class StorageServiceInstance(t.TypedDict):
    service_name: t.Literal["storage_service"]
    device_id: int


class AppComponentBase(t.TypedDict):
    name: str


class AppComponent(AppComponentBase, total=False):
    device: str
    group_owner: str
    # According to the manual:
    # Description of business impact due to loss of component.
    what: str
    depends_on: str
    # Comma separated list
    dependents: str
    device_reason: str
    # list of string pairs for dependent appcomps on this appcomp e.g.
    # depend_appcomp_name1:reason1, depend_appcomp_name2:reason2
    depends_on_reasons: str


class CustomFieldBase(t.TypedDict):
    """
    Editing a custom field should be as simple as sending these to
    the relevant API.

    Getting them is a little trickier, for now I created a DOQL Query.
    """

    # ID of whichever other object you're editing
    id: int
    key: str
    value: str


class ServiceInstanceCustomField(CustomFieldBase, total=False):
    """POST/PUT: /api/1.0/custom_fields/serviceinstance

    GET: /data/v1.0/query/?saved_query_name
    =get_service_instance_custom_fields
    &delimiter=,&header=yes&output_type=json
    """

    serviceinstance_fk: int
    service_name: str
    type_id: int
    type: str
    related_model_name: t.Optional[int]
    filterable: bool
    mandatory: bool
    log_for_api: bool
    is_multi: bool
    notes: str


class CustomerBase(t.TypedDict):
    name: str


class Customer(CustomerBase, total=False):
    contact_info: str
    notes: str
    type: t.Literal["customer", "department"]
    # Used for renaming customers.
    new_name: str
    """
    From the docs:

    ```
    If multitenancy is on,
    admin groups that have access to this object are specified here.

    e.g. "Prod_East:no,Corp:yes "

    Specifies that the admin groups for this object are Prod_East with view
    only permission and Corp with change permission.

    If this parameter is present with no value, all groups are deleted.
    ```
    """
    groups: str


class BuildingBase(t.TypedDict):
    name: str
    address: str


class Building(BuildingBase, total=False):
    contact_name: str
    contact_phone: str
    notes: str
    groups: str
    longitude: str
    latitude: str
    building_id: int


class RoomBase(t.TypedDict):
    name: str


class Room(RoomBase, total=False):
    contact_name: str
    contact_phone: str
    notes: str
    groups: str
    longitude: str
    latitude: str
    building_id: int
    # default to numeric
    horizontal_grid_numbering: t.Literal["numeric", "alphabetic"]
    vertical_grid_numbering: t.Literal["numeric", "alphabetic"]
    horizontal_grid_start: str
    vertical_grid_start: str
    # unit of measurement (meters or inches)
    uom: t.Literal["m", "in"]
    height: str
    grid_rows: str
    grid_cols: str
    raised_floor: t.Literal["yes", "no"]
    raised_floor_height: str
    reverse_xaxis: t.Literal["yes", "no"]
    reverse_yaxis: t.Literal["yes", "no"]
    room_id: int
