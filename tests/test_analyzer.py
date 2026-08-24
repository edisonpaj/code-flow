from pathlib import Path
from backend.flow_analyzer import analyze
from backend.java_parser import endpoints, parse_project


def test_hexagonal_flow(tmp_path: Path):
    source = tmp_path / "src/main/java/example"
    source.mkdir(parents=True)
    (tmp_path / "pom.xml").write_text("<artifactId>spring-boot-starter-web</artifactId>")
    (source / "ClienteController.java").write_text('''package example;
@RestController
@RequestMapping("/api/clientes")
public class ClienteController {
private final AtualizarUseCase useCase;
@PutMapping("/{id}")
public void atualizar() { useCase.executar(); }
}''')
    (source / "AtualizarUseCase.java").write_text("package example; public interface AtualizarUseCase { void executar(); }")
    (source / "AtualizarService.java").write_text('''package example;
public class AtualizarService implements AtualizarUseCase {
private final ClienteRepositoryPort repository;
public void executar() { repository.buscarPorId(); }
}''')
    (source / "ClienteRepositoryPort.java").write_text("package example; public interface ClienteRepositoryPort { void buscarPorId(); }")
    (source / "ClienteRepositoryAdapter.java").write_text('''package example;
public class ClienteRepositoryAdapter implements ClienteRepositoryPort {
public void buscarPorId() { }
}''')
    parsed = parse_project(tmp_path)
    endpoint = endpoints(parsed)[0]
    result = analyze(str(tmp_path), endpoint["id"])
    assert endpoint["path"] == "/api/clientes/{id}"
    assert [step["class_name"] for step in result["steps"]] == [
        "ClienteController", "AtualizarUseCase", "AtualizarService",
        "ClienteRepositoryPort", "ClienteRepositoryAdapter"]
