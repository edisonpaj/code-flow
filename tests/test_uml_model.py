import tempfile
import unittest
from pathlib import Path
from backend.flow_analyzer import analyze
from backend.java_parser import endpoints, parse_project


JAVA = {
"adapter/in/web/ClienteController.java": '''package example;
@RestController
@RequestMapping("/api/clientes")
public class ClienteController {
private final AtualizarUseCase useCase;
@PutMapping("/{id}")
public String atualizar(String id) { return useCase.executar(id); }
}''',
"application/port/in/AtualizarUseCase.java": "package example; public interface AtualizarUseCase { String executar(String id); }",
"application/service/AtualizarService.java": '''package example;
public class AtualizarService implements AtualizarUseCase {
private final ClienteRepositoryPort repository;
public String executar(String id) { String atual = buscar(id); if (id.isBlank()) { repository.existe(id); } else { repository.auditar(id); } if (repository.existe(id)) { throw new ClienteJaExisteException(); } for (int i=0;i<1;i++) { repository.auditar(id); } return repository.salvar(atual); }
public String buscar(String id) { return repository.buscarPorId(id); } }''',
"application/port/out/ClienteRepositoryPort.java": "package example; public interface ClienteRepositoryPort { String buscarPorId(String id); }",
"adapter/out/persistence/ClienteRepositoryAdapter.java": '''package example;
public class ClienteRepositoryAdapter implements ClienteRepositoryPort {
private final SpringDataClienteRepository repository;
public String buscarPorId(String id) { return repository.findById(id); }
public boolean existe(String id) { return repository.existsById(id); }
public void auditar(String id) { repository.count(); }
public String salvar(String value) { return repository.save(value); } }''',
"adapter/out/persistence/SpringDataClienteRepository.java": "package example; public interface SpringDataClienteRepository extends JpaRepository { }",
"adapter/out/persistence/ClientePersistenceMapper.java": '''package example;
public class ClientePersistenceMapper {
public static String paraDominio(String entity) { return entity; }
}''',
"adapter/in/web/ClienteResponse.java": '''package example;
public record ClienteResponse(String value) {
public static ClienteResponse de(String cliente) { return new ClienteResponse(cliente); }
}''',
}


class UmlModelTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root / "pom.xml").write_text("<artifactId>spring-boot-starter-web</artifactId>")
        for relative, source in JAVA.items():
            path = self.root / "src/main/java/example" / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source)
        endpoint = endpoints(parse_project(self.root))[0]
        self.result = analyze(str(self.root), endpoint["id"]); self.model = self.result["model"]

    def tearDown(self): self.temp.cleanup()

    def test_actor_and_instance_classifier_participants(self):
        self.assertEqual(self.model["participants"][0]["type"], "actor")
        self.assertIn("service:AtualizarService", [p["display"] for p in self.model["participants"]])

    def test_nested_calls_have_parent_and_depth(self):
        calls = self.model["calls"]
        self.assertTrue(all("parent_call_id" in call and "depth" in call for call in calls))
        self.assertGreater(max(call["depth"] for call in calls), 2)

    def test_self_call(self):
        call = next(call for call in self.model["calls"] if call["method"] == "buscar")
        self.assertTrue(call["self_call"])

    def test_interface_resolves_to_implementation(self):
        contract = next(call for call in self.model["calls"] if call["method"] == "executar" and call.get("contract_dispatch"))
        call = next(call for call in self.model["calls"] if call["method"] == "executar" and not call.get("contract_dispatch"))
        self.assertEqual(contract["callee"], "AtualizarUseCase")
        self.assertEqual(call["callee"], "AtualizarService")
        self.assertEqual(call["resolved_from"], "AtualizarUseCase")

    def test_hexagonal_ports_are_explicit_in_sequence(self):
        calls = self.model["calls"]
        use_case = next(call for call in calls if call["callee"] == "AtualizarUseCase")
        service = next(call for call in calls if call["callee"] == "AtualizarService")
        output_port = next(call for call in calls if call["callee"] == "ClienteRepositoryPort")
        adapter = next(call for call in calls if call["callee"] == "ClienteRepositoryAdapter" and call["method"] == "buscarPorId")
        self.assertEqual(use_case["caller"], "ClienteController")
        self.assertEqual(service["caller"], "AtualizarUseCase")
        self.assertEqual(output_port["caller"], "AtualizarService")
        self.assertEqual(adapter["caller"], "ClienteRepositoryPort")
        layers = {participant["classifier"]: participant["layer"] for participant in self.model["participants"]}
        self.assertEqual(layers["AtualizarUseCase"], "Port IN")
        self.assertEqual(layers["ClienteRepositoryPort"], "Port OUT")
        self.assertEqual(layers["SpringDataClienteRepository"], "Framework/Database")

    def test_returns_follow_descendants_in_reverse_order(self):
        events = self.model["events"]
        find_call = next(e for e in events if e["type"] == "call" and e["method"] == "findById")
        adapter_call = next(e for e in events if e["type"] == "call" and e["method"] == "buscarPorId")
        find_return = next(i for i,e in enumerate(events) if e["type"] == "return" and e["call_id"] == find_call["id"])
        adapter_return = next(i for i,e in enumerate(events) if e["type"] == "return" and e["call_id"] == adapter_call["id"])
        self.assertLess(find_return, adapter_return)

    def test_opt_loop_exception_and_spring_data(self):
        calls = self.model["calls"]
        self.assertTrue(any(c.get("fragment", {}).get("operator") == "loop" for c in calls if c.get("fragment")))
        exception = next(e for e in self.model["events"] if e["type"] == "exception")
        self.assertEqual(exception["fragment"]["operator"], "opt")
        self.assertTrue(any(p["layer"] == "Framework/Database" for p in self.model["participants"]))

    def test_mermaid_uses_activation_return_and_frame(self):
        mermaid = self.result["mermaid"]
        self.assertIn("->>+", mermaid); self.assertIn("-->>-", mermaid)
        self.assertIn("sd PUT /api/clientes/{id}", mermaid)
        self.assertIn("loop", mermaid); self.assertIn("opt", mermaid)
        self.assertIn("alt ", mermaid); self.assertIn("else", mermaid)

    def test_static_factory_and_mapper_method_reference_are_included(self):
        owner = self.root / "src/main/java/example/adapter/in/web/ClienteController.java"
        owner.write_text('''package example;
@RestController @RequestMapping("/api/clientes")
public class ClienteController {
private final AtualizarUseCase useCase;
@GetMapping("/{id}")
public ClienteResponse buscar(String id) {
String cliente = useCase.executar(id);
return ClienteResponse.de(cliente);
}
}''')
        adapter = self.root / "src/main/java/example/adapter/out/persistence/ClienteRepositoryAdapter.java"
        adapter.write_text('''package example;
public class ClienteRepositoryAdapter implements ClienteRepositoryPort {
private final SpringDataClienteRepository repository;
public String buscarPorId(String id) {
return repository.findById(id).map(ClientePersistenceMapper::paraDominio);
}
}''')
        endpoint = next(item for item in endpoints(parse_project(self.root)) if item["http_method"] == "GET")
        result = analyze(str(self.root), endpoint["id"])
        calls = [(call["callee"], call["method"]) for call in result["model"]["calls"]]
        self.assertIn(("ClientePersistenceMapper", "paraDominio"), calls)
        self.assertIn(("ClienteResponse", "de"), calls)


if __name__ == "__main__": unittest.main()
