import copy
from pathlib import Path

import pytest

from cdsim_common.manifests import (
    ManifestKind,
    area_semantic_errors,
    discover,
    load_yaml,
    platform_semantic_errors,
    rubric_semantic_errors,
    schema_errors,
)
from cdsim_common.paths import repo_root

ROOT = repo_root()
assert ROOT is not None
SCHEMAS = ROOT / "schemas" / "json"



def test_repo_manifests_are_all_valid() -> None:
    found, errors = discover(
        SCHEMAS,
        platforms_dir=ROOT / "platforms",
        areas_dir=ROOT / "terrain" / "areas",
        rubrics_dir=ROOT / "services" / "assessment" / "rubrics",
        scenarios_dir=ROOT / "scenarios",
    )
    assert errors == []
    assert "cdpl_quad_01" in found.platforms
    assert {"hyd_demo_01", "flat_test"} <= set(found.areas)
    assert "precision_landing_v1" in found.rubrics
    assert "landing_motor_failure_01" in found.scenarios


def test_template_platform_is_skipped() -> None:
    found, _ = discover(SCHEMAS, platforms_dir=ROOT / "platforms")
    assert not any(k.startswith("_") for k in found.platforms)


@pytest.fixture
def quad() -> dict:  # type: ignore[type-arg]
    return load_yaml(ROOT / "platforms" / "cdpl_quad_01" / "platform.yaml")


def test_schema_rejects_unknown_class(quad: dict) -> None:  # type: ignore[type-arg]
    quad["class"] = "submarine"
    assert any("class" in e for e in schema_errors(quad, ManifestKind.PLATFORM, SCHEMAS))


def test_failure_mode_must_target_declared_actuator(quad: dict) -> None:  # type: ignore[type-arg]
    quad["failure_modes"][0]["effect"]["target"] = "m9"
    assert any("m9" in e for e in platform_semantic_errors(quad, "cdpl_quad_01"))


def test_procedure_tool_must_exist(quad: dict) -> None:  # type: ignore[type-arg]
    quad["maintenance"]["procedures"][0]["steps"][2]["tool_id"] = "sonic_screwdriver"
    assert any("sonic_screwdriver" in e for e in platform_semantic_errors(quad))


def test_platform_id_must_match_dir(quad: dict) -> None:  # type: ignore[type-arg]
    assert platform_semantic_errors(quad, "other_dir")


def test_area_pad_outside_bounds() -> None:
    area = load_yaml(ROOT / "terrain" / "areas" / "flat_test" / "area.yaml")
    bad = copy.deepcopy(area)
    bad["landing_pads"][0]["position"]["lat_deg"] = 0.0
    assert any("outside bounds" in e for e in area_semantic_errors(bad))
    assert area_semantic_errors(area, "flat_test") == []


def test_rubric_band_order() -> None:
    rub = load_yaml(ROOT / "services" / "assessment" / "rubrics" / "precision_landing_v1.yaml")
    assert rubric_semantic_errors(rub) == []
    rub["metrics"][0]["bands"][0]["limit"] = 5.0
    assert any("best→worst" in e for e in rubric_semantic_errors(rub))


def test_scenario_with_unknown_pad(tmp_path: Path) -> None:
    src = (ROOT / "scenarios" / "landing_motor_failure_01.yaml").read_text()
    (tmp_path / "s.yaml").write_text(src.replace("pad_alpha", "pad_zulu"))
    _, errors = discover(
        SCHEMAS,
        platforms_dir=ROOT / "platforms",
        areas_dir=ROOT / "terrain" / "areas",
        rubrics_dir=ROOT / "services" / "assessment" / "rubrics",
        scenarios_dir=tmp_path,
    )
    assert len(errors) == 1 and "pad_zulu" in str(errors[0])
