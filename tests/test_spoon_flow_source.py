from pathlib import Path

import backend.flow_analyzer as flow_analyzer
from backend.java_parser import endpoints, parse_project


def test_spoon_edges_drive_the_rendered_flow(monkeypatch, tmp_path: Path):
    source = tmp_path / "src/main/java/demo"
    source.mkdir(parents=True)
    (source / "ClienteController.java").write_text('''package demo;
@RestController
public class ClienteController {
private final ClienteService service;
@GetMapping("/clientes")
public void listar() { service.listar(); }
}''')
    (source / "ClienteService.java").write_text('''package demo;
public class ClienteService {
private final ClienteRepository repository;
public void listar() { repository.findAll(); }
}''')
    (source / "ClienteRepository.java").write_text('''package demo;
public class ClienteRepository {
public void findAll() { }
}''')
    report = {"calls": [
        {"caller_type": "demo.ClienteController", "caller_method": "listar",
         "callee_type": "demo.ClienteService", "callee_method": "listar", "arguments": [], "line": 6},
        {"caller_type": "demo.ClienteService", "caller_method": "listar",
         "callee_type": "demo.ClienteRepository", "callee_method": "findAll", "arguments": [], "line": 4},
    ]}
    monkeypatch.setattr(flow_analyzer, "analyze_with_spoon", lambda *_args, **_kwargs:
                        {"state": "ready", "report": report, "authoritative": False})
    endpoint = endpoints(parse_project(tmp_path))[0]
    result = flow_analyzer.analyze(str(tmp_path), endpoint["id"], "spoon-hybrid")
    assert result["analysis_engine"]["active"] == "spoon"
    assert result["analysis_engine"]["flow_source"] == "spoon-source-call-graph"
    assert [step["class_name"] for step in result["steps"]] == [
        "ClienteController", "ClienteService", "ClienteRepository"]


def test_spoon_does_not_reuse_python_only_edges(monkeypatch, tmp_path: Path):
    source = tmp_path / "src/main/java/demo"
    source.mkdir(parents=True)
    (source / "Controller.java").write_text('''package demo;
@RestController public class Controller {
private final Service service;
@GetMapping("/x")
public void get() { service.run(); }
}''')
    (source / "Service.java").write_text("package demo; public class Service { public void run() {} }")
    monkeypatch.setattr(flow_analyzer, "analyze_with_spoon", lambda *_args, **_kwargs:
                        {"state": "ready", "report": {"calls": []}, "authoritative": False})
    endpoint = endpoints(parse_project(tmp_path))[0]
    result = flow_analyzer.analyze(str(tmp_path), endpoint["id"], "spoon-hybrid")
    assert [step["class_name"] for step in result["steps"]] == ["Controller"]


def test_sootup_bytecode_edges_are_merged_with_spoon_source(monkeypatch, tmp_path: Path):
    source = tmp_path / "src/main/java/demo"
    source.mkdir(parents=True)
    (source / "Controller.java").write_text('''package demo;
@RestController
public class Controller {
private final UseCase useCase;
@GetMapping("/x")
public void get() { useCase.run(); Response.de(); }
}''')
    (source / "UseCase.java").write_text("package demo; public interface UseCase { void run(); }")
    (source / "Service.java").write_text('''package demo;
public class Service implements UseCase { public void run() {} }''')
    (source / "Response.java").write_text('''package demo;
public class Response { public static void de() {} }''')
    report = {
        "calls": [{"caller_type": "demo.Controller", "caller_method": "get",
                   "callee_type": "demo.Response", "callee_method": "de", "arguments": [], "line": 4}],
        "sootup": {"state": "ready", "calls": [
            {"caller_type": "demo.Controller", "caller_method": "get",
             "callee_type": "demo.UseCase", "callee_method": "run", "arguments": [], "ordinal": 2}],
            "hierarchy": [{"type": "demo.Service", "interfaces": ["demo.UseCase"],
                           "all_interfaces": ["demo.UseCase"]}]}}
    monkeypatch.setattr(flow_analyzer, "analyze_with_spoon", lambda *_args, **_kwargs:
                        {"state": "ready", "report": report, "authoritative": False})
    endpoint = endpoints(parse_project(tmp_path))[0]
    result = flow_analyzer.analyze(str(tmp_path), endpoint["id"], "spoon-hybrid")
    assert result["analysis_engine"]["flow_source"] == "spoon-sootup-call-graph"
    assert [step["class_name"] for step in result["steps"]] == ["Controller", "UseCase", "Service", "Response"]


def test_typed_call_metadata_keeps_call_and_method_returns_separate(monkeypatch, tmp_path: Path):
    source = tmp_path / "src/main/java/demo"
    source.mkdir(parents=True)
    (source / "PedidoController.java").write_text('''package demo;
@RestController
public class PedidoController {
private final PedidoService service;
@GetMapping("/pedidos/{id}")
public Pedido buscarPorId(@PathVariable UUID id) { return service.buscarPorId(id); }
}''')
    (source / "PedidoService.java").write_text('''package demo;
public class PedidoService {
private final PedidoRepository repository;
public Pedido buscarPorId(UUID id) { return repository.findById(id).orElseThrow(); }
}''')
    (source / "PedidoRepository.java").write_text(
        "package demo; public interface PedidoRepository extends JpaRepository<Pedido, UUID> {}")
    (source / "Pedido.java").write_text("package demo; public class Pedido {}")
    report = {"calls": [
        {"caller_type": "demo.PedidoController", "caller_method": "buscarPorId",
         "callee_type": "demo.PedidoService", "callee_method": "buscarPorId",
         "target": "service", "receiver_type": "demo.PedidoService", "arguments": ["id"],
         "argument_details": [{"expression": "id", "name": "id", "type": "java.util.UUID"}],
         "method_parameters": [{"name": "id", "type": "java.util.UUID", "annotations": ["PathVariable"]}],
         "call_return_type": "demo.Pedido", "method_return_type": "demo.Pedido", "line": 4},
        {"caller_type": "demo.PedidoService", "caller_method": "buscarPorId",
         "callee_type": "demo.PedidoRepository", "callee_method": "findById",
         "target": "repository", "receiver_type": "demo.PedidoRepository", "arguments": ["id"],
         "argument_details": [{"expression": "id", "name": "id", "type": "java.util.UUID"}],
         "method_parameters": [{"name": "id", "type": "java.util.UUID", "annotations": []}],
         "call_return_type": "java.util.Optional<demo.Pedido>", "method_return_type": "demo.Pedido", "line": 4},
    ]}
    monkeypatch.setattr(flow_analyzer, "analyze_with_spoon", lambda *_args, **_kwargs:
                        {"state": "ready", "report": report, "authoritative": False})
    endpoint = endpoints(parse_project(tmp_path))[0]
    result = flow_analyzer.analyze(str(tmp_path), endpoint["id"], "spoon-hybrid")
    controller_step = result["steps"][0]
    assert controller_step["method_parameters"] == [
        {"name": "id", "type": "UUID", "annotations": ["PathVariable"]}]
    assert controller_step["method_return_type"] == "Pedido"
    service_call = next(call for call in result["model"]["calls"] if call.get("object_reference") == "service")
    repository_call = next(call for call in result["model"]["calls"] if call.get("object_reference") == "repository")
    assert service_call["object_reference"] == "service"
    assert service_call["object_type"] == "PedidoService"
    assert service_call["argument_details"] == [{"expression": "id", "name": "id", "type": "UUID"}]
    assert service_call["call_return_type"] == "Pedido"
    assert repository_call["object_reference"] == "repository"
    assert repository_call["object_type"] == "PedidoRepository"
    assert repository_call["call_return_type"] == "Optional<Pedido>"
    assert repository_call["method_return_type"] == "Pedido"
