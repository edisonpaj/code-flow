import unittest
from tempfile import TemporaryDirectory

from backend.analyzer.maturity_catalog import maturity_dimensions_catalog
from backend.analyzer.maturity_evaluator import evaluate_dimension


class MaturityCatalogTest(unittest.TestCase):
    def test_has_six_dimensions_and_auditable_criteria(self):
        catalog = maturity_dimensions_catalog()
        self.assertEqual(catalog["summary"]["dimensions"], 6)
        self.assertEqual(catalog["summary"]["criteria"], 69)
        self.assertEqual(catalog["summary"]["subdimensions"], 38)
        self.assertEqual([item["id"] for item in catalog["dimensions"]],
                         ["CODE_QUALITY", "SOFTWARE_DESIGN", "RESILIENCE", "SECURITY", "OBSERVABILITY", "OPERABILITY"])
        for dimension in catalog["dimensions"]:
            self.assertTrue(dimension["description"])
            for criterion in dimension["criteria"]:
                self.assertTrue(all(criterion[field] for field in
                                    ("id", "subdimension", "criterion", "evaluates", "sources", "expected_evidence", "tool")))

    def test_design_contains_expected_subdimensions(self):
        catalog = maturity_dimensions_catalog()
        design = next(item for item in catalog["dimensions"] if item["id"] == "SOFTWARE_DESIGN")
        self.assertEqual({"Padrão Arquitetural", "Separação de Responsabilidades", "Direção das Dependências",
                          "Isolamento do Domínio", "Acoplamento", "Integrações"},
                         {item["subdimension"] for item in design["criteria"]})

    def test_observability_is_independent(self):
        catalog = maturity_dimensions_catalog()
        observability = next(item for item in catalog["dimensions"] if item["id"] == "OBSERVABILITY")
        self.assertEqual(len(observability["criteria"]), 9)

    def test_integration_inventory_is_informational_and_gateway_controls_are_external(self):
        catalog = maturity_dimensions_catalog()
        inventory = next(rule for dimension in catalog["dimensions"] for rule in dimension["criteria"] if rule["id"] == "DS-INT-001")
        security = next(item for item in catalog["dimensions"] if item["id"] == "SECURITY")
        self.assertFalse(inventory["score_enabled"])
        self.assertEqual(security["external_controls"]["owner"], "API Gateway")

    def test_subdimension_structure_matches_the_published_contract(self):
        catalog = maturity_dimensions_catalog()
        expected = {
            "CODE_QUALITY": ["Stack & Build", "Orientação a Objetos", "SOLID", "Manutenibilidade", "Tratamento de Erros", "Testabilidade"],
            "SOFTWARE_DESIGN": ["Padrão Arquitetural", "Separação de Responsabilidades", "Direção das Dependências", "Isolamento do Domínio", "Acoplamento", "Integrações"],
            "RESILIENCE": ["Timeout", "Circuit Breaker", "Retry", "Bulkhead", "Fallback / Degradação", "Mensageria Resiliente"],
            "SECURITY": ["Validação de Entrada", "Secrets e Credenciais", "Proteção de Dados", "Tratamento Seguro de Erros", "Segurança das Integrações", "Dependências Vulneráveis", "Configuração Segura", "Logging Seguro"],
            "OBSERVABILITY": ["Health", "Logging", "Métricas", "Tracing", "Correlação", "Diagnóstico de Erros"],
            "OPERABILITY": ["Build / Empacotamento", "Container", "Kubernetes / OpenShift", "Recursos", "Health Operacional", "Escalabilidade"],
        }
        self.assertEqual({dimension["id"]: dimension["subdimensions"] for dimension in catalog["dimensions"]}, expected)

    def test_main_dimension_names_and_codes_match_the_published_contract(self):
        catalog = maturity_dimensions_catalog()
        self.assertEqual([(dimension["display_code"], dimension["name"]) for dimension in catalog["dimensions"]], [
            ("01", "Qualidade de Código"),
            ("02", "Design de Software"),
            ("03", "Resiliência"),
            ("04", "Segurança"),
            ("05", "Observabilidade"),
            ("06", "Operabilidade"),
        ])

    def test_every_catalog_criterion_is_emitted_by_the_evaluator(self):
        catalog = maturity_dimensions_catalog()
        expected = {criterion["id"] for dimension in catalog["dimensions"] for criterion in dimension["criteria"]}
        with TemporaryDirectory() as project:
            results = [evaluate_dimension(project, dimension["id"]) for dimension in catalog["dimensions"]]
        emitted = [criterion for dimension in results for criterion in dimension["criteria"]]
        self.assertEqual({criterion["id"] for criterion in emitted}, expected)
        self.assertEqual(len(emitted), len(expected))
        self.assertTrue(all(criterion["processing_status"] in {"EVALUATED", "NOT_EVALUATED"} for criterion in emitted))
        self.assertTrue(all(criterion["criterionId"] == criterion["id"] for criterion in emitted))


if __name__ == "__main__": unittest.main()
