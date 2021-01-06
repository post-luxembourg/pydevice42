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

HTTP_METHODS = t.Literal["GET", "POST", "PUT"]
STATUS = t.Literal["USED", "UNUSED"]
T = t.TypeVar("T")


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
