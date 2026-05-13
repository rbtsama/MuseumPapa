"""Structural tests on config files. Catches typos / missing fields without
needing the network."""
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEEDS = REPO / "config" / "library_seeds.json"
LIBCAL = REPO / "config" / "platform_pass_ids" / "libcal.json"
MK = REPO / "config" / "platform_pass_ids" / "museumkey.json"
BPL = REPO / "config" / "platform_pass_ids" / "bpl.json"

EXPECTED_PLATFORM_COUNTS = {"assabet": 52, "libcal": 5, "museumkey": 2}
REQUIRED_LIB_FIELDS = (
    "id",
    "name",
    "town",
    "network",
    "platform",
    "domain",
    "supports_availability",
)


def _load_seeds():
    return json.loads(SEEDS.read_text(encoding="utf-8"))["libraries"]


def test_seeds_total_count_59():
    libs = _load_seeds()
    assert len(libs) == 59


def test_seeds_platform_split():
    libs = _load_seeds()
    counts = Counter(l["platform"] for l in libs)
    assert dict(counts) == EXPECTED_PLATFORM_COUNTS


def test_seeds_no_duplicate_ids():
    libs = _load_seeds()
    ids = [l["id"] for l in libs]
    assert len(ids) == len(set(ids))


def test_seeds_all_have_required_fields():
    libs = _load_seeds()
    for l in libs:
        missing = [k for k in REQUIRED_LIB_FIELDS if k not in l]
        assert not missing, f"{l.get('id')!r} missing fields: {missing}"


def test_museumkey_marked_catalog_only():
    libs = _load_seeds()
    mk = [l for l in libs if l["platform"] == "museumkey"]
    assert all(l["supports_availability"] is False for l in mk)
    other = [l for l in libs if l["platform"] != "museumkey"]
    assert all(l["supports_availability"] is True for l in other)


def test_libcal_id_map_libraries_match_seeds():
    """LibCal map covers the 4 non-BPL libcal libs in seeds."""
    seeds_libcal = {l["id"] for l in _load_seeds() if l["platform"] == "libcal"} - {"bpl"}
    map_libs = set(json.loads(LIBCAL.read_text(encoding="utf-8"))["libraries"].keys())
    assert seeds_libcal == map_libs, f"seeds={seeds_libcal} map={map_libs}"


def test_museumkey_id_map_libraries_match_seeds():
    seeds_mk = {l["id"] for l in _load_seeds() if l["platform"] == "museumkey"}
    map_libs = set(json.loads(MK.read_text(encoding="utf-8"))["libraries"].keys())
    assert seeds_mk == map_libs


def test_bpl_passes_count_23():
    bpl = json.loads(BPL.read_text(encoding="utf-8"))
    assert len(bpl["passes"]) == 23


def test_libcal_per_library_passes_present():
    """Each LibCal lib has at least 9 passes mapped (lowest is Milton)."""
    libs = json.loads(LIBCAL.read_text(encoding="utf-8"))["libraries"]
    for lib_id, info in libs.items():
        assert info.get("domain"), f"{lib_id} missing domain"
        assert (
            len(info.get("passes", {})) >= 9
        ), f"{lib_id} only has {len(info.get('passes', {}))} passes mapped"


def test_museumkey_per_library_code_branch():
    libs = json.loads(MK.read_text(encoding="utf-8"))["libraries"]
    for lib_id, params in libs.items():
        assert params.get("code"), f"{lib_id} missing code"
        assert isinstance(params.get("branchID"), int), f"{lib_id} branchID not int"


def test_museumkey_name_to_benefit_nonempty():
    mk = json.loads(MK.read_text(encoding="utf-8"))
    assert len(mk["name_to_benefit"]) >= 20
