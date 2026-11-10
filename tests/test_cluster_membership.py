"""Semantic regression cases: explicit source states and actual displayed incidence."""
import copy
import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cluster_contract", ROOT / "scripts/check_cluster_membership.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClusterContractTests(unittest.TestCase):
    def setUp(self):
        self.clusters = [dict(cluster_id="c1", window_id="window-1", candidate_snp="variant-A",
                              cluster_pp="0.83", candidate_snp_posterior_fraction="0.12",
                              trait_set="Exposure|A|C"),
                         dict(cluster_id="c2", window_id="window-2", candidate_snp="variant-A",
                              cluster_pp="0.91", trait_set="Exposure|B")]
        self.members = [dict(cluster_id=row["cluster_id"], trait=t, in_input="true",
                             in_cluster=str(t in row["trait_set"].split("|")).lower())
                        for row in self.clusters for t in ["Exposure", "A", "B", "C"]]
        self.plotted = [dict(cluster_id=r["cluster_id"], trait=r["trait"])
                        for r in self.members if r["in_cluster"] == "true"]

    def check(self, **kwargs):
        return MODULE.audit(self.clusters, self.members, threshold=0.7, **kwargs)

    def test_exact_members_and_separate_snp_fraction(self):
        result = self.check(rendered=self.plotted)
        self.assertEqual((result["clusters"], result["members"], result["source_cells"]), (2, 5, 8))
        self.assertEqual(result["cluster_records"]["c1"]["cluster_pp"], 0.83)
        self.assertEqual(result["cluster_records"]["c1"]["candidate_snp_posterior_fraction"], "0.12")
        self.assertFalse(result["actual_render_validated"])

    def test_same_candidate_in_distinct_records_is_not_merged(self):
        self.assertEqual(self.check()["clusters"], 2)

    def test_declared_universe_detects_deleted_entire_zero_column(self):
        self.members += [dict(cluster_id=r["cluster_id"], trait="Zero", in_input="false", in_cluster="false")
                         for r in self.clusters]
        declared = ["Exposure", "A", "B", "C", "Zero"]
        self.assertEqual(self.check(source_traits=declared)["trait_universe"], "declared_and_checked")
        self.members = [r for r in self.members if r["trait"] != "Zero"]
        with self.assertRaisesRegex(MODULE.ContractError, "declared source universe"):
            self.check(source_traits=declared)
        self.assertEqual(self.check()["trait_universe"], "observed_in_input_only")

    def test_compact_order_can_omit_zero_member_source_trait(self):
        self.members += [dict(cluster_id=r["cluster_id"], trait="Zero", in_input="false", in_cluster="false")
                         for r in self.clusters]
        links = [dict(cluster_id="c1", left_trait="Exposure", right_trait="A")]
        result = self.check(connectors=links, trait_order=["Exposure", "A", "B", "C"],
                            source_traits=["Exposure", "A", "B", "C", "Zero"])
        self.assertEqual(result["traits"], 5)

    def test_duplicate_cluster_rejected(self):
        self.clusters.append(copy.deepcopy(self.clusters[0]))
        with self.assertRaisesRegex(MODULE.ContractError, "duplicate cluster_id"):
            self.check()

    def test_duplicate_source_cell_rejected(self):
        self.members.append(copy.deepcopy(self.members[0]))
        with self.assertRaisesRegex(MODULE.ContractError, "duplicate membership"):
            self.check()

    def test_member_cannot_be_outside_input(self):
        self.members[0]["in_input"] = "false"
        with self.assertRaisesRegex(MODULE.ContractError, "outside the regional input"):
            self.check()

    def test_explicit_unknown_states_required(self):
        self.members.pop(2)  # Remove a non-member cell; positives alone are insufficient.
        with self.assertRaisesRegex(MODULE.ContractError, "every row/trait state"):
            self.check()

    def test_member_sets_must_match_exactly(self):
        self.members[1]["in_cluster"] = "false"
        with self.assertRaisesRegex(MODULE.ContractError, "member set mismatch"):
            self.check()

    def test_pp_boundary_and_nonfinite_rejected(self):
        for value in ["0.7", "NaN", "inf", "1.1", "-0.1"]:
            with self.subTest(value=value):
                self.clusters[0]["cluster_pp"] = value
                with self.assertRaises(MODULE.ContractError):
                    self.check()

    def test_invalid_fraction_cannot_hide_behind_valid_cluster_pp(self):
        self.clusters[0]["candidate_snp_posterior_fraction"] = "NaN"
        with self.assertRaises(MODULE.ContractError):
            self.check()

    def test_missing_extra_and_duplicate_render_marks_rejected(self):
        for marks in [self.plotted[:-1], self.plotted + [dict(cluster_id="c1", trait="B")],
                      self.plotted + [self.plotted[0]]]:
            with self.subTest(marks=marks), self.assertRaises(MODULE.ContractError):
                self.check(rendered=marks)

    def test_connector_cannot_cross_blank(self):
        links = [dict(cluster_id="c1", left_trait="A", right_trait="C")]
        with self.assertRaisesRegex(MODULE.ContractError, "crosses a non-member"):
            self.check(connectors=links, trait_order=["Exposure", "A", "B", "C"])

    def test_contiguous_true_member_connector_accepted(self):
        links = [dict(cluster_id="c1", left_trait="Exposure", right_trait="A")]
        self.assertEqual(self.check(connectors=links, trait_order=["Exposure", "A", "B", "C"])["status"], "PASS")

    def test_bad_boolean_and_empty_source_rejected(self):
        with self.assertRaises(MODULE.ContractError):
            MODULE.boolean("unknown")
        with self.assertRaises(MODULE.ContractError):
            MODULE.audit([], [], threshold=.7)

    def test_cli_positive_and_failed_output_overwrites_pass(self):
        demo = ROOT / "examples/cluster-membership"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "audit.json"
            args = [sys.executable, str(ROOT / "scripts/check_cluster_membership.py"),
                    "--clusters", str(demo / "clusters.tsv"), "--memberships", str(demo / "memberships.tsv"),
                    "--rendered-memberships", str(demo / "plotted-members.tsv"),
                    "--source-traits", "Exposure|Trait_A|Trait_B|Trait_C|Trait_D",
                    "--pp-threshold", ".7", "--out", str(out)]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(out.read_text())["status"], "PASS")
            args[args.index(".7")] = ".95"
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(out.read_text())["status"], "FAIL")

    def test_demo_renderer_exports_same_members_and_neutral_guides(self):
        demo = ROOT / "examples/cluster-membership"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(demo / "render_demo.py"), "--out", tmp],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            import xml.etree.ElementTree as ET
            svg = ET.parse(Path(tmp) / "preview.svg").getroot()
            marks = [(n.get("data-cluster"), n.get("data-trait")) for n in svg.iter()
                     if n.get("class") == "member"]
            rows = MODULE.table(demo / "plotted-members.tsv", ["cluster_id", "trait"])
            self.assertEqual(set(marks), {(r["cluster_id"], r["trait"]) for r in rows})
            self.assertEqual(len(marks), len(rows))
            self.assertEqual(len([n for n in svg.iter() if n.get("class") == "reading-guide"]), 2)
            html = (Path(tmp) / "preview.html").read_text()
            self.assertIn("Synthetic illustration", html)
            self.assertIn('tabindex="0"', html)

    @unittest.skipUnless(shutil.which("node"), "Node unavailable; optional DOM event-logic replay only")
    def test_single_active_row_mouse_keyboard_and_escape_logic(self):
        # A small DOM double verifies state transitions, not browser layout/accessibility.
        program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const details={textContent:'initial'},events={};let document;
function row(name){const classes=new Set(),attributes={'aria-label':name},handlers={};return {
  dataset:{detail:'details '+name},classList:{toggle:(key,on)=>on?classes.add(key):classes.delete(key)},
  setAttribute:(key,value)=>attributes[key]=value,getAttribute:key=>attributes[key],
  addEventListener:(key,callback)=>handlers[key]=callback,
  blur:()=>{document.activeElement=null;handlers.blur?.()},classes,attributes,handlers
};}
const rows=[row('A'),row('B')];
document={querySelectorAll:()=>rows,getElementById:()=>details,addEventListener:(key,cb)=>events[key]=cb,activeElement:null};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{document});
function active(index){assert.equal(rows.filter(r=>r.classes.has('active')).length,index===null?0:1);if(index!==null)assert(rows[index].classes.has('active'));}
document.activeElement=rows[0];rows[0].handlers.focus();rows[0].handlers.click();active(0);
rows[1].handlers.mouseenter();active(1);assert.equal(details.textContent,'details B');
rows[1].handlers.mouseleave();active(0);assert.equal(details.textContent,'details A');
rows[0].blur();active(0);rows[0].handlers.click();active(null);assert.equal(details.textContent,'initial');
document.activeElement=rows[1];rows[1].handlers.focus();rows[1].handlers.keydown({key:'Enter',preventDefault(){}});active(1);
events.keydown({key:'Escape'});active(null);assert.equal(details.textContent,'initial');
assert(rows.every(r=>r.attributes['aria-pressed']==='false'));
'''
        result = subprocess.run(["node", "-e", program, str(ROOT / "scripts/cluster_reading.js")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
