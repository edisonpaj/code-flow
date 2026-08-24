import unittest

from backend.analyzer.semantic.catalog import semantic_catalog


class SemanticCatalogTest(unittest.TestCase):
    def test_catalog_exposes_versioned_rules_and_mappings(self):
        catalog = semantic_catalog()
        self.assertGreater(catalog["summary"]["exact_rules"], 0)
        self.assertGreater(catalog["summary"]["return_rules"], 0)
        self.assertTrue(all(rule["id"] and rule["source_file"].endswith("semantic_rules.py") for rule in catalog["rules"]))
        self.assertIn("DELETE", {item["intent"] for item in catalog["intent_mappings"]})
        self.assertIn("FIND", {item["operation_kind"] for item in catalog["operation_mappings"]})

    def test_delete_find_rule_is_visible(self):
        rules = semantic_catalog()["rules"]
        rule = next(item for item in rules if item["source_role"] == "APPLICATION_SERVICE"
                    and item["target_role"] == "PERSISTENCE_ADAPTER"
                    and item["endpoint_intent"] == "DELETE" and item["operation_kind"] == "FIND")
        self.assertEqual(rule["template"], "Verifica existência do {entity}")


if __name__ == "__main__": unittest.main()
