import tempfile
import unittest
from pathlib import Path

from backend.analyzer.architecture_classifier import classify_project
from backend.flow_analyzer import analyze
from backend.java_parser import endpoints, parse_project
from backend.analyzer.semantic.endpoint_intent import EndpointIntent, detect_endpoint_intent
from backend.analyzer.semantic.operation_classifier import OperationKind, classify_operation

SOURCES = {
"adapter/in/ClienteController.java": '''package demo;
@RestController
@RequestMapping("/api/v1/clientes")
public class ClienteController {
private final ListarUseCase useCase;
@GetMapping
public String listar() { return useCase.listar(); }
}''',
"application/port/in/ListarUseCase.java": "package demo; public interface ListarUseCase { String listar(); }",
"application/service/ClienteService.java": '''package demo;
@Service
public class ClienteService implements ListarUseCase {
private final ClienteRepositoryPort port;
public String listar() { return port.listar(); }
}''',
"application/port/out/ClienteRepositoryPort.java": "package demo; public interface ClienteRepositoryPort { String listar(); }",
"adapter/out/ClientePersistenceAdapter.java": '''package demo;
public class ClientePersistenceAdapter implements ClienteRepositoryPort {
private final SpringDataClienteRepository repository;
public String listar() { return repository.findAll(); }
}''',
"adapter/out/SpringDataClienteRepository.java": "package demo; public interface SpringDataClienteRepository extends JpaRepository<Cliente, Long> { }",
"external/ClienteFeign.java": "package demo; @FeignClient(name=\"cliente\") public interface ClienteFeign { }",
"misc/Helper.java": "package demo; public class Helper { }",
}

class SemanticPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        for relative, content in SOURCES.items():
            path = self.root / "src/main/java/demo" / relative
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)

    def tearDown(self): self.temp.cleanup()

    def test_spring_role_classification(self):
        result = classify_project(parse_project(self.root))
        expected = {"ClienteController": "HTTP_ENTRYPOINT", "ClienteService": "APPLICATION_SERVICE",
                    "ListarUseCase": "USE_CASE_PORT", "ClienteRepositoryPort": "PERSISTENCE_PORT",
                    "ClientePersistenceAdapter": "PERSISTENCE_ADAPTER", "SpringDataClienteRepository": "DATABASE_REPOSITORY",
                    "ClienteFeign": "HTTP_CLIENT", "Helper": "UNKNOWN"}
        for name, role in expected.items(): self.assertEqual(result[name]["role"], role)

    def test_semantic_flow_and_both_mermaid_modes(self):
        endpoint = endpoints(parse_project(self.root))[0]; result = analyze(str(self.root), endpoint["id"])
        roles = [p["role"] for p in result["semantic_flow"]["participants"]]
        self.assertEqual(roles, ["ACTOR", "HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY"])
        self.assertNotIn("stream", result["architectural_mermaid"])
        self.assertIn("API de Clientes", result["architectural_mermaid"])
        self.assertIn("ClienteController", result["technical_mermaid"])

    def test_endpoint_intents(self):
        cases = [("GET", "/clientes", EndpointIntent.LIST), ("GET", "/clientes/{id}", EndpointIntent.READ),
                 ("POST", "/clientes", EndpointIntent.CREATE), ("PUT", "/clientes/{id}", EndpointIntent.UPDATE),
                 ("PATCH", "/clientes/{id}", EndpointIntent.UPDATE), ("DELETE", "/clientes/{id}", EndpointIntent.DELETE)]
        for method, path, expected in cases: self.assertEqual(detect_endpoint_intent(method, path), expected)

    def test_operation_kinds(self):
        cases = [("findById", OperationKind.FIND), ("findAll", OperationKind.FIND_ALL),
                 ("save", OperationKind.SAVE), ("deleteById", OperationKind.DELETE)]
        for method, expected in cases: self.assertEqual(classify_operation(method), expected)

    def test_delete_keeps_find_and_delete_relations(self):
        controller = self.root / "src/main/java/demo/adapter/in/ClienteController.java"
        controller.write_text(controller.read_text().replace(
            '@GetMapping\npublic String listar() { return useCase.listar(); }',
            '@DeleteMapping("/{id}")\n@ResponseStatus(HttpStatus.NO_CONTENT)\npublic void excluir(String id) { useCase.excluir(id); }'))
        (self.root / "src/main/java/demo/application/port/in/ListarUseCase.java").write_text(
            "package demo; public interface ListarUseCase { void excluir(String id); }")
        (self.root / "src/main/java/demo/application/service/ClienteService.java").write_text('''package demo;
@Service public class ClienteService implements ListarUseCase {
private final ClienteRepositoryPort port;
public void excluir(String id) { buscarPorId(id); port.excluirPorId(id); }
public String buscarPorId(String id) { return port.buscarPorId(id); }
}''')
        (self.root / "src/main/java/demo/application/port/out/ClienteRepositoryPort.java").write_text(
            "package demo; public interface ClienteRepositoryPort { String buscarPorId(String id); void excluirPorId(String id); }")
        (self.root / "src/main/java/demo/adapter/out/ClientePersistenceAdapter.java").write_text('''package demo;
public class ClientePersistenceAdapter implements ClienteRepositoryPort {
private final SpringDataClienteRepository repository;
public String buscarPorId(String id) { return repository.findById(id); }
public void excluirPorId(String id) { repository.deleteById(id); }
}''')
        endpoint = endpoints(parse_project(self.root))[0]; result = analyze(str(self.root), endpoint["id"])
        descriptions = [item["functional_description"] for item in result["semantic_flow"]["interactions"]]
        self.assertIn("Verifica existência do cliente", descriptions)
        self.assertIn("Solicita remoção do cliente", descriptions)
        self.assertIn("Remove registro do cliente", descriptions)
        self.assertNotIn("resultado", result["architectural_mermaid"])
        self.assertIn("HTTP 204", result["architectural_mermaid"])

if __name__ == "__main__": unittest.main()
