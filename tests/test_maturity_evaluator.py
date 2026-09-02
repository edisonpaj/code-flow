import tempfile
import unittest
from pathlib import Path

from backend.maturity.evaluator import consolidate, evaluate_dimension
from backend.maturity.scoring import dimension_score


class MaturityEvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        (root/"src/main/java/demo/domain").mkdir(parents=True);(root/"src/main/resources").mkdir(parents=True)
        (root/"src/main/java/demo/domain/Cliente.java").write_text("package demo.domain; class Cliente { private String nome; public void alterarNome(String nome){this.nome=nome;} }",encoding="utf-8")
        (root/"src/main/java/demo/Client.java").write_text("package demo; class Client { private final WebClient webClient; @CircuitBreaker(name=\"x\") void call(){} }",encoding="utf-8")
        (root/"src/main/resources/application.yml").write_text("password: ${DB_PASSWORD}\nclient:\n  responseTimeout: 2s\n",encoding="utf-8")
        (root/"pom.xml").write_text("<project><properties><java.version>21</java.version></properties><parent><artifactId>spring-boot-starter-parent</artifactId><version>3.4.1</version></parent></project>",encoding="utf-8")
        self.root=str(root)
    def tearDown(self):self.temp.cleanup()
    def test_resilience_applies_and_scores_objective_evidence(self):
        result=evaluate_dimension(self.root,"RESILIENCE");criteria={r["id"]:r for r in result["criteria"]}
        self.assertEqual(criteria["RES-CB-001"]["result"],"ADHERENT")
        self.assertEqual(criteria["RES-TIMEOUT-001"]["result"],"ADHERENT")
        self.assertEqual(criteria["RES-CB-001"]["criterionId"],"RES-CB-001")
        self.assertIn("tool",criteria["RES-CB-001"])
        self.assertIsInstance(criteria["RES-CB-001"]["confidence"],float)
        self.assertEqual(criteria["RES-CB-001"]["dimension"],"RESILIENCE")
        self.assertGreater(result["coverage_percent"],0)
    def test_resilience_is_evaluated_but_not_applicable_without_integration(self):
        Path(self.root,"src/main/java/demo/Client.java").write_text("package demo; class Client {}",encoding="utf-8")
        result=evaluate_dimension(self.root,"RESILIENCE")
        resilience=result["criteria"]
        self.assertTrue(all(r["processing_status"]=="EVALUATED" for r in resilience))
        self.assertTrue(all(r["result"]=="NOT_APPLICABLE" for r in resilience))
    def test_not_evaluated_is_zero_and_not_applicable_is_excluded(self):
        score,coverage,confidence,evaluated,applicable=dimension_score([
            {"processing_status":"EVALUATED","result":"ADHERENT","score":1.0},
            {"processing_status":"EVALUATED","result":"NOT_APPLICABLE","score":None},
            {"processing_status":"NOT_EVALUATED","result":None,"score":None},
        ])
        self.assertEqual(score,50);self.assertEqual(coverage,50);self.assertEqual(confidence,"LOW")
        self.assertEqual(evaluated,1);self.assertEqual(applicable,2)
    def test_subdimensions_have_equal_weight_inside_dimension(self):
        score,_,_,_,_=dimension_score([
            {"subdimension":"A","processing_status":"EVALUATED","result":"ADHERENT","score":1.0},
            {"subdimension":"B","processing_status":"EVALUATED","result":"NON_ADHERENT","score":0.0},
            {"subdimension":"B","processing_status":"EVALUATED","result":"NON_ADHERENT","score":0.0},
            {"subdimension":"B","processing_status":"EVALUATED","result":"NON_ADHERENT","score":0.0},
        ])
        self.assertEqual(score,50)

    def test_operability_does_not_fail_on_multistage_dockerfile_rule(self):
        Path(self.root, "Dockerfile").write_text(
            "FROM maven:3.9-eclipse-temurin-21 AS build\n"
            "COPY . .\n"
            "FROM eclipse-temurin:21-jre\n"
            "USER 1001\n",
            encoding="utf-8",
        )
        result = evaluate_dimension(self.root, "OPERABILITY")
        criteria = {item["id"]: item for item in result["criteria"]}
        self.assertEqual(criteria["OPS-CONT-003"]["result"], "ADHERENT")
        self.assertEqual(result["dimension_id"], "OPERABILITY")

    def test_consolidation_uses_processing_result_model(self):
        summary=consolidate([evaluate_dimension(self.root,"SECURITY"),evaluate_dimension(self.root,"CODE_QUALITY")])
        self.assertIn("foundation",summary);self.assertLess(summary["coverage_percent"],100)
        self.assertEqual(summary["method"],"SIX_DIMENSIONS_OBJECTIVE_MODEL_1.0")


if __name__=="__main__":unittest.main()
