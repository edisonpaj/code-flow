import unittest
from pathlib import Path
from backend.architecture_detector import detect_architecture
from backend.models import JavaType


def java_type(name, layer, kind="class", interfaces=None):
    return JavaType(name=name, kind=kind, path=Path(name + ".java"), package="test", layer=layer,
                    interfaces=interfaces or [])


class ArchitectureDetectorTest(unittest.TestCase):
    def test_detects_hexagonal(self):
        types = {
            "ClienteController": java_type("ClienteController", "Adapter IN"),
            "AtualizarUseCase": java_type("AtualizarUseCase", "Port IN", "interface"),
            "ClienteService": java_type("ClienteService", "Service", interfaces=["AtualizarUseCase"]),
            "ClienteRepositoryPort": java_type("ClienteRepositoryPort", "Port OUT", "interface"),
            "ClienteRepositoryAdapter": java_type("ClienteRepositoryAdapter", "Adapter OUT", interfaces=["ClienteRepositoryPort"]),
        }
        result = detect_architecture(types)
        self.assertEqual(result["type"], "HEXAGONAL")
        self.assertIn("Port IN", result["expected_flow"])

    def test_detects_layered(self):
        types = {
            "ClienteController": java_type("ClienteController", "Controller"),
            "ClienteService": java_type("ClienteService", "Service"),
            "ClienteRepository": java_type("ClienteRepository", "Repository", "interface"),
            "ClienteEntity": java_type("ClienteEntity", "Entity"),
        }
        result = detect_architecture(types)
        self.assertEqual(result["type"], "LAYERED")
        self.assertEqual(result["expected_flow"], ["Controller", "Service", "Repository", "Database"])

    def test_does_not_force_a_pattern_without_evidence(self):
        result = detect_architecture({"App": java_type("App", "Java")})
        self.assertEqual(result["type"], "UNKNOWN")


if __name__ == "__main__": unittest.main()
