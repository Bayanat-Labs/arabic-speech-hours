import os

import yaml

from arabic_speech_hours.build import classify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = yaml.safe_load(open(os.path.join(ROOT, "config", "licence_classes.yaml")))["string_rules"]


def test_open_commercial():
    for s in ["cc0-1.0", "cc-by-4.0", "cc-by-3.0", "cc-by-sa-4.0", "odc-by", "pddl"]:
        assert classify(s, RULES)[0] == "open-commercial", s


def test_software_licence_flag():
    assert classify("mit", RULES) == ("open-commercial", "software_licence_on_data")
    assert classify("apache-2.0", RULES) == ("open-commercial", "software_licence_on_data")


def test_nc_and_nd():
    assert classify("cc-by-nc-4.0", RULES)[0] == "open-noncommercial"
    assert classify("cc-by-nc-sa-4.0", RULES)[0] == "open-noncommercial"
    assert classify("cc-by-nc-2.0", RULES)[0] == "open-noncommercial"
    assert classify("cc-by-nd-4.0", RULES)[0] == "no-derivatives"
    assert classify("cc-by-nc-nd-4.0", RULES)[0] == "no-derivatives"


def test_research_and_unknown():
    assert classify("research-use", RULES)[0] == "research-or-request"
    assert classify("none", RULES)[0] == "unknown"
    assert classify(None, RULES)[0] == "unknown"
    assert classify("something-else", RULES)[0] == "unknown"
