import re
from pathlib import Path
from .implementation_resolver import implementation_index, resolve
from .java_parser import parse_project, endpoints
from .architecture_detector import detect_architecture
from .analyzer.architecture_classifier import classify_project
from .analyzer.semantic_flow import build_semantic_flow, semantic_mermaid
from .analyzer.semantic.endpoint_intent import build_endpoint_context
from .spoon_bridge import analyze_with_spoon

MEMBER_CALL_RE = re.compile(r"\b(\w+)\s*\.\s*(\w+)\s*\(")
METHOD_REFERENCE_RE = re.compile(r"\b(\w+)\s*::\s*(\w+)\b")
LOCAL_CALL_RE = re.compile(r"(?<![.\w])([a-zA-Z_]\w*)\s*\(")
CONTROL_RE = re.compile(r"\b(if|for|while|switch)\s*\((.*?)\)\s*\{", re.DOTALL)
IGNORED_RECEIVERS = {"this", "super", "return", "stream", "Optional"}
IGNORED_CALLS = {"if", "for", "while", "switch", "catch", "throw", "new", "return", "super", "this"}
LAYER_ORDER = {"Actor": 0, "Adapter IN": 10, "Port IN": 20, "Service": 30, "Domain": 40,
               "Controller": 10, "Port OUT": 50, "Adapter OUT": 60, "Repository": 65,
               "Entity": 70, "Infrastructure": 75, "Java": 80, "External": 90}


def _method(owner, name):
    return next((method for method in owner.methods if method.name == name), None)


def _inherited_return_type(owner, method_name: str) -> str | None:
    """Resolve somente contratos Spring Data comprovados pela herança genérica."""
    bases = owner.extends or []
    repository_at = next((index for index, name in enumerate(bases)
                          if name in {"JpaRepository", "CrudRepository", "PagingAndSortingRepository"}), None)
    if repository_at is None or repository_at + 1 >= len(bases): return None
    entity = bases[repository_at + 1]
    return {"findById": f"Optional<{entity}>", "findAll": f"List<{entity}>",
            "save": entity, "delete": "void", "deleteById": "void",
            "existsById": "boolean", "count": "long"}.get(method_name)


def _display_type(value: str | None) -> str | None:
    if not value: return value
    return re.sub(r"(?:[a-z_]\w*\.)+([A-Z]\w*)", r"\1", value)


def _method_parameter_details(parameters: str) -> list[dict]:
    """Best-effort fallback when the structural Java analyzer is not active."""
    result = []
    for raw in [part.strip() for part in parameters.split(",") if part.strip()]:
        annotations = re.findall(r"@(\w+)(?:\([^)]*\))?", raw)
        declaration = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", raw).strip()
        match = re.search(r"([\w<>?,.\[\]]+)\s+(\w+)$", declaration)
        if match:
            result.append({"name": match.group(2), "type": _display_type(match.group(1)),
                           "annotations": annotations})
    return result


def _balanced_end(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == opening: depth += 1
        elif text[pos] == closing:
            depth -= 1
            if depth == 0: return pos
    return len(text)


def _controls(body: str) -> list[dict]:
    regions = []
    for match in CONTROL_RE.finditer(body):
        brace = body.find("{", match.start())
        kind, condition = match.group(1), " ".join(match.group(2).split())
        group_id = f"fragment-{match.start()}"
        operator = "loop" if kind in {"for", "while"} else ("alt" if kind == "switch" else "opt")
        end = _balanced_end(body, brace, "{", "}")
        else_match = re.match(r"\s*else\s*\{", body[end + 1:]) if kind == "if" else None
        if else_match:
            operator = "alt"
            else_brace = body.find("{", end + 1); else_end = _balanced_end(body, else_brace, "{", "}")
            regions.append({"operator": operator, "condition": condition, "start": brace, "end": end,
                            "group_id": group_id, "branch": "if"})
            regions.append({"operator": operator, "condition": "else", "start": else_brace, "end": else_end,
                            "group_id": group_id, "branch": "else"})
            continue
        regions.append({"operator": operator, "condition": condition, "start": brace, "end": end,
                        "group_id": group_id, "branch": "main"})
    if ".stream()" in body or ".forEach(" in body:
        regions.append({"operator": "loop", "condition": "para cada elemento do stream", "start": 0, "end": len(body), "group_id": "stream", "branch": "main"})
    if "CompletableFuture" in body:
        regions.append({"operator": "par", "condition": "execução concorrente", "start": 0, "end": len(body), "group_id": "concurrent", "branch": "main"})
    return regions


def _fragment_at(regions: list[dict], position: int) -> dict | None:
    matches = [r for r in regions if r["start"] <= position <= r["end"]]
    if not matches: return None
    region = min(matches, key=lambda r: r["end"] - r["start"])
    return {"operator": region["operator"], "condition": region["condition"],
            "group_id": region["group_id"], "branch": region["branch"]}


def _calls(owner, method, index, types):
    calls, regions = [], _controls(method.body)
    for match in MEMBER_CALL_RE.finditer(method.body):
        receiver, called = match.group(1), match.group(2)
        if receiver in IGNORED_RECEIVERS: continue
        declared = owner.fields.get(receiver)
        # A receiver beginning with an uppercase letter is commonly a Java type,
        # e.g. ClienteResponse.de(cliente).  These static factory/mapper calls are
        # part of the endpoint flow and must not be discarded.
        static_target = receiver if receiver in types else None
        target = resolve(declared, index, types) if declared else (static_target or (owner.name if _method(owner, called) else None))
        if not target: continue
        begin = method.body.find("(", match.start()); end = _balanced_end(method.body, begin, "(", ")")
        args = " ".join(method.body[begin + 1:end].split())
        calls.append((match.start(), target, called, args, declared if declared and target != declared else None, _fragment_at(regions, match.start())))
    # Covers transformations passed to Optional/Stream as method references,
    # such as result.map(ClientePersistenceMapper::paraDominio).
    for match in METHOD_REFERENCE_RE.finditer(method.body):
        receiver, called = match.group(1), match.group(2)
        target = receiver if receiver in types else None
        if not target or not _method(types[target], called): continue
        calls.append((match.start(), target, called, "resultado", None, _fragment_at(regions, match.start())))
    for match in LOCAL_CALL_RE.finditer(method.body):
        called = match.group(1)
        if called in IGNORED_CALLS or not _method(owner, called): continue
        begin = method.body.find("(", match.start()); end = _balanced_end(method.body, begin, "(", ")")
        args = " ".join(method.body[begin + 1:end].split())
        calls.append((match.start(), owner.name, called, args, None, _fragment_at(regions, match.start())))
    return sorted(calls, key=lambda call: call[0])


def _instance_name(class_name: str, layer: str) -> str:
    special = {"Actor": "client", "Adapter IN": "controller", "Controller": "controller", "Service": "service",
               "Adapter OUT": "repositoryAdapter", "Repository": "repository", "Port OUT": "port", "Infrastructure": "infrastructure"}
    if "Repository" in class_name and "Adapter" not in class_name: return "jpaRepository"
    return special.get(layer, class_name[0].lower() + class_name[1:])


def _architecture_context(layer: str, contract: str | None, caller_layer: str | None, architecture: str) -> dict:
    descriptions = {
        "Adapter IN": "Adaptador de entrada: recebe a requisição HTTP e traduz para um caso de uso.",
        "Controller": "Camada Controller: recebe HTTP e delega a execução para a camada de serviço.",
        "Port IN": "Porta de entrada: contrato pelo qual os adaptadores acionam a aplicação.",
        "Service": "Aplicação: orquestra o caso de uso sem depender diretamente de infraestrutura.",
        "Domain": "Domínio: concentra regras e modelos de negócio.",
        "Port OUT": "Porta de saída: contrato usado pela aplicação para acessar recursos externos.",
        "Adapter OUT": "Adaptador de saída: implementa uma porta e traduz para tecnologia externa.",
        "Repository": "Camada Repository: concentra o acesso a dados na arquitetura em camadas.",
        "Entity": "Camada de entidades persistentes da aplicação.",
        "Framework/Database": "Infraestrutura/framework: operação concreta de persistência.",
        "Infrastructure": "Infraestrutura: detalhe técnico externo ao núcleo da aplicação.",
        "Java": "Componente Java sem camada hexagonal identificada pelo caminho.",
    }
    relation = f"{caller_layer} → {layer}" if caller_layer else f"Entrada HTTP → {layer}"
    if contract: relation += f" via {contract}"
    return {"role": descriptions.get(layer, descriptions["Java"]), "relation": relation,
            "boundary_crossing": bool(caller_layer and caller_layer != layer), "architecture": architecture}


def analyze(project_value: str, endpoint_id: str, analysis_engine: str = "python-legacy") -> dict:
    if analysis_engine not in {"python-legacy", "spoon-hybrid"}:
        raise ValueError("Motor de análise inválido")
    project = Path(project_value).resolve()
    spoon_analysis = analyze_with_spoon(str(project), requested=analysis_engine == "spoon-hybrid")
    types = parse_project(project)
    endpoint = next((item for item in endpoints(types) if item["id"] == endpoint_id), None)
    if not endpoint: raise ValueError("Endpoint não encontrado")
    index = implementation_index(types); architecture = detect_architecture(types)
    classifications = classify_project(types)
    spoon_ready = analysis_engine == "spoon-hybrid" and spoon_analysis.get("state") == "ready"
    if spoon_ready:
        report = spoon_analysis.get("report", {})
        structural_relations = []
        for item in report.get("types", []):
            implementation = (item.get("simple_name") or "").rsplit(".", 1)[-1]
            for contract in item.get("interfaces", []):
                structural_relations.append((contract.rsplit(".", 1)[-1], implementation))
        for item in report.get("sootup", {}).get("hierarchy", []):
            implementation = (item.get("type") or "").rsplit(".", 1)[-1]
            for contract in [*item.get("interfaces", []), *item.get("all_interfaces", [])]:
                structural_relations.append((contract.rsplit(".", 1)[-1], implementation))
        for contract, implementation in structural_relations:
            if contract in types and implementation in types:
                candidates = index.setdefault(contract, [])
                if implementation not in candidates: candidates.append(implementation)
    spoon_call_index: dict[tuple[str, str], list[dict]] = {}
    if spoon_ready:
        report = spoon_analysis["report"]
        source_evidence = report.get("calls", [])
        bytecode_evidence = report.get("sootup", {}).get("calls", [])
        combined_evidence, evidence_positions = [], {}
        # Prefer bytecode for method dispatch and retain source-only calls such as
        # method references/factories that may compile through invokedynamic.
        for evidence in [*bytecode_evidence, *source_evidence]:
            key = ((evidence.get("caller_type") or "").rsplit(".", 1)[-1],
                   evidence.get("caller_method") or "",
                   (evidence.get("callee_type") or evidence.get("receiver_type") or "").rsplit(".", 1)[-1],
                   evidence.get("callee_method") or "")
            if key in evidence_positions:
                # Spoon preserves source-level argument names; use them to replace
                # SootUp stack temporaries while keeping bytecode target resolution.
                if evidence.get("evidence_source") == "source":
                    current = combined_evidence[evidence_positions[key]]
                    current["arguments"] = evidence.get("arguments") or current.get("arguments", [])
                    current["line"] = evidence.get("line") or current.get("line", 0)
                    for detail_key in ("target", "receiver_type", "method_parameters", "method_return_type",
                                       "argument_details", "call_return_type", "signature"):
                        if evidence.get(detail_key) is not None: current[detail_key] = evidence[detail_key]
                continue
            evidence_positions[key] = len(combined_evidence); combined_evidence.append(dict(evidence))
        for evidence in combined_evidence:
            caller_type = (evidence.get("caller_type") or "").rsplit(".", 1)[-1].split("$")[0]
            caller_method = evidence.get("caller_method") or ""
            spoon_call_index.setdefault((caller_type, caller_method), []).append(evidence)
        for evidence_list in spoon_call_index.values():
            evidence_list.sort(key=lambda item: (item.get("line") or item.get("ordinal") or 0,
                                                  item.get("callee_method", "")))

    def discovered_calls(owner, method):
        if not spoon_ready:
            return [(*item, {}) for item in _calls(owner, method, index, types)]
        result = []
        for evidence in spoon_call_index.get((owner.name, method.name), []):
            called = evidence.get("callee_method") or ""
            declared_type = evidence.get("receiver_type") or evidence.get("callee_type") or ""
            declared = declared_type.rsplit(".", 1)[-1].split("$")[0]
            target = declared if declared in types else (owner.name if _method(owner, called) else None)
            if not target or called in IGNORED_CALLS:
                continue
            concrete = resolve(target, index, types) or target
            via = target if concrete != target else None
            arguments = ", ".join(evidence.get("arguments") or [])
            result.append((evidence.get("line") or evidence.get("ordinal") or 0,
                           target, called, arguments, via, None, evidence))
        return result
    participants = {"client": {"id": "client", "instance": "client", "classifier": "Cliente/API Client",
                               "display": "Cliente/API Client", "type": "actor", "layer": "Actor", "order": 0}}
    calls, events, descriptive = [], [], []
    counter = 0

    def participant(type_name: str) -> str:
        owner = types[type_name]; pid = re.sub(r"\W", "", type_name)
        role_layer = {"HTTP_ENTRYPOINT": "Adapter IN", "USE_CASE_PORT": "Port IN",
                      "APPLICATION_SERVICE": "Service", "PERSISTENCE_PORT": "Port OUT",
                      "PERSISTENCE_ADAPTER": "Adapter OUT", "DATABASE_REPOSITORY": "Framework/Database"}
        runtime_layer = role_layer.get(classifications.get(type_name, {}).get("role"), owner.layer)
        contracts = [interface for interface, implementations in index.items() if type_name in implementations]
        instance = _instance_name(type_name, runtime_layer)
        participants[pid] = {"id": pid, "instance": instance, "classifier": type_name,
                             "display": f"{instance}:{type_name}", "type": "participant", "layer": runtime_layer,
                             "contracts": contracts, "file": str(owner.path),
                             "line": owner.methods[0].line if owner.methods else 1,
                             "order": 80 if runtime_layer == "Framework/Database" else LAYER_ORDER.get(owner.layer, 80)}
        return pid

    def invoke(caller, type_name, method_name, args, parent_id, depth, via=None, fragment=None, active=(), call_meta=None):
        nonlocal counter
        call_meta = call_meta or {}
        concrete = resolve(type_name, index, types) or type_name; owner = types.get(concrete)
        if not owner or depth > 24: return
        contract_return = None
        if via and via in types and via != concrete:
            contract_owner = types[via]; contract_method = _method(contract_owner, method_name)
            contract_callee = participant(via); counter += 1; contract_id = f"call-{counter}"
            signature = f"{method_name}({args})" if args else f"{method_name}()"
            contract_call = {"id": contract_id, "parent_call_id": parent_id, "caller": caller,
                             "callee": contract_callee, "method": method_name, "arguments": args,
                             "signature": signature, "message_type": "synchronous", "depth": depth,
                             "line": contract_method.line if contract_method else 1,
                             "file": str(contract_owner.path),
                             "return_type": contract_method.return_type if contract_method else "resultado",
                             "fragment": fragment, "resolved_from": None, "self_call": False,
                             "contract_dispatch": True}
            calls.append(contract_call); events.append({"type": "call", **contract_call})
            contract_layer = participants[contract_callee]["layer"]
            contract_context = _architecture_context(contract_layer, None,
                                                       participants.get(caller, {}).get("layer"), architecture["type"])
            try: contract_relative = str(contract_owner.path.relative_to(project))
            except ValueError: contract_relative = contract_owner.path.name
            descriptive.append({"order": len(descriptive) + 1, "class_name": via, "method": method_name,
                                "label": f"{via}.{signature}", "interface": via, "layer": contract_layer,
                                "line": contract_call["line"], "file": contract_call["file"],
                                "call_id": contract_id, "relative_file": contract_relative,
                                "package": contract_owner.package, "arguments": args,
                                "return_type": contract_call["return_type"], "depth": depth,
                                "parent_call_id": parent_id, "resolved_from": None,
                                "caller": participants.get(caller, {}).get("display", caller),
                                "callee": participants[contract_callee]["display"], "contracts": [],
                                "hexagonal_role": contract_context["role"],
                                "architecture_relation": contract_context["relation"],
                                "boundary_crossing": contract_context["boundary_crossing"],
                                "architecture_type": architecture["type"], "contract_dispatch": True})
            contract_return = (contract_callee, caller, contract_id, parent_id, depth,
                               contract_call["return_type"])
            caller, parent_id, depth = contract_callee, contract_id, depth + 1
        callee = participant(concrete); method = _method(owner, method_name); counter += 1; call_id = f"call-{counter}"
        signature = f"{method_name}({args})" if args else f"{method_name}()"
        reported_return = call_meta.get("call_return_type")
        call_return_type = ((reported_return if reported_return not in {None, "", "unknown", "<unknown>"} else None)
                            or (method.return_type if method else None)
                            or _inherited_return_type(owner, method_name) or "unknown")
        method_return_type = call_meta.get("method_return_type") or "unknown"
        argument_details = call_meta.get("argument_details") or [{"expression": value.strip(), "name": value.strip() if re.fullmatch(r"\w+", value.strip()) else None, "type": None} for value in args.split(",") if value.strip()]
        method_parameters = call_meta.get("method_parameters") or []
        typed_arguments = ", ".join(f"{item.get('expression', '')}: {_display_type(item.get('type'))}"
                                    if item.get("type") else item.get("expression", "") for item in argument_details)
        signature = f"{method_name}({typed_arguments})"
        call_return_type = _display_type(call_return_type) or "unknown"
        method_return_type = _display_type(method_return_type) or "unknown"
        for item in argument_details: item["type"] = _display_type(item.get("type"))
        for item in method_parameters: item["type"] = _display_type(item.get("type"))
        call = {"id": call_id, "parent_call_id": parent_id, "caller": caller, "callee": callee,
                "method": method_name, "arguments": args, "signature": signature, "message_type": "synchronous",
                "depth": depth, "line": method.line if method else 1, "file": str(owner.path),
                "return_type": call_return_type, "call_return_type": call_return_type,
                "method_return_type": method_return_type, "method_parameters": method_parameters,
                "argument_details": argument_details, "object_reference": call_meta.get("target"),
                "object_type": _display_type(call_meta.get("receiver_type")),
                "from_class": (call_meta.get("caller_type") or "").rsplit(".", 1)[-1] or None,
                "from_method": call_meta.get("caller_method"), "to_class": concrete, "to_method": method_name,
                "fragment": fragment,
                "resolved_from": via, "self_call": caller == callee,
                "semantic_caller": contract_return[1] if contract_return else caller}
        calls.append(call); events.append({"type": "call", **call})
        caller_layer = participants.get(caller, {}).get("layer")
        runtime_layer = participants[callee]["layer"]
        context = _architecture_context(runtime_layer, via, caller_layer, architecture["type"])
        try: relative_file = str(owner.path.relative_to(project))
        except ValueError: relative_file = owner.path.name
        descriptive.append({"order": len(descriptive) + 1, "class_name": concrete, "method": method_name,
                            "label": f"{concrete}.{signature}", "interface": via, "layer": runtime_layer,
                            "line": call["line"], "file": call["file"], "call_id": call_id,
                            "relative_file": relative_file, "package": owner.package,
                            "arguments": args, "return_type": call["return_type"],
                            "call_return_type": call_return_type, "method_return_type": method_return_type,
                            "method_parameters": method_parameters, "argument_details": argument_details,
                            "object_reference": call_meta.get("target"), "object_type": _display_type(call_meta.get("receiver_type")),
                            "depth": depth, "parent_call_id": parent_id, "resolved_from": via,
                            "caller": participants.get(caller, {}).get("display", caller),
                            "callee": participants[callee]["display"], "contracts": participants[callee].get("contracts", []),
                            "hexagonal_role": context["role"], "architecture_relation": context["relation"],
                            "boundary_crossing": context["boundary_crossing"], "architecture_type": architecture["type"]})
        key = (concrete, method_name)
        if method and key not in active:
            for _, target, called, child_args, child_via, child_fragment, child_meta in discovered_calls(owner, method):
                invoke(callee, target, called, child_args, call_id, depth + 1, child_via, child_fragment, active + (key,), child_meta)
        if method and not spoon_ready:
            regions = _controls(method.body)
            for thrown in re.finditer(r"throw\s+new\s+(\w+)", method.body):
                events.append({"type": "exception", "call_id": call_id, "parent_call_id": parent_id,
                               "from": callee, "to": caller, "exception": thrown.group(1), "depth": depth,
                               "fragment": _fragment_at(regions, thrown.start())})
        events.append({"type": "return", "call_id": call_id, "parent_call_id": parent_id, "from": callee,
                       "to": caller, "value": call_return_type, "depth": depth})
        if contract_return:
            source, target, contract_id, contract_parent, contract_depth, return_type = contract_return
            events.append({"type": "return", "call_id": contract_id, "parent_call_id": contract_parent,
                           "from": source, "to": target, "value": return_type, "depth": contract_depth})

    controller = participant(endpoint["controller"]); controller_owner = types[endpoint["controller"]]
    controller_method = _method(controller_owner, endpoint["method"]); counter += 1; root_id = f"call-{counter}"
    interaction = f"{endpoint['http_method']} {endpoint['path']}"
    root_evidence = next(iter(spoon_call_index.get((endpoint["controller"], endpoint["method"]), [])), {})
    root_parameters = root_evidence.get("method_parameters") or (
        _method_parameter_details(controller_method.parameters) if controller_method else [])
    for item in root_parameters: item["type"] = _display_type(item.get("type"))
    root_method_return = _display_type(root_evidence.get("method_return_type") or (
        controller_method.return_type if controller_method else None)) or "unknown"
    root = {"id": root_id, "parent_call_id": None, "caller": "client", "callee": controller,
            "method": endpoint["method"], "arguments": "", "signature": f"{interaction} → {endpoint['method']}()", "message_type": "synchronous",
            "depth": 0, "line": endpoint["line"], "file": "", "return_type": "HTTP Response",
            "method_parameters": root_parameters, "method_return_type": root_method_return,
            "fragment": None, "resolved_from": None, "self_call": False}
    calls.append(root); events.append({"type": "call", **root})
    root_context = _architecture_context(controller_owner.layer, None, "Actor", architecture["type"])
    descriptive.append({"order": 1, "class_name": endpoint["controller"], "method": endpoint["method"],
                        "label": f"{endpoint['controller']}.{endpoint['method']}()", "interface": None,
                        "layer": controller_owner.layer, "line": endpoint["line"], "file": str(controller_owner.path),
                        "relative_file": str(controller_owner.path.relative_to(project)), "package": controller_owner.package,
                        "arguments": "", "return_type": controller_method.return_type if controller_method else "HTTP Response",
                        "method_parameters": root_parameters, "method_return_type": root_method_return,
                        "call_id": root_id, "depth": 0, "parent_call_id": None, "resolved_from": None,
                        "caller": "Cliente/API Client", "callee": participants[controller]["display"],
                        "contracts": participants[controller].get("contracts", []),
                        "hexagonal_role": root_context["role"], "architecture_relation": root_context["relation"],
                        "boundary_crossing": True, "architecture_type": architecture["type"]})
    if controller_method:
        for _, target, called, child_args, child_via, child_fragment, child_meta in discovered_calls(controller_owner, controller_method):
            invoke(controller, target, called, child_args, root_id, 1, child_via, child_fragment,
                   ((endpoint["controller"], endpoint["method"]),), child_meta)
    events.append({"type": "return", "call_id": root_id, "parent_call_id": None, "from": controller,
                   "to": "client", "value": "HTTP Response", "depth": 0})
    ordered = sorted(participants.values(), key=lambda p: (p["order"], p["display"]))
    model = {"interaction": interaction, "participants": ordered, "calls": calls, "events": events,
             "architecture": architecture}
    endpoint_context = build_endpoint_context(endpoint, types)
    endpoint["intent"] = endpoint_context.intent
    endpoint["entity"] = endpoint_context.entity
    semantic_flow = build_semantic_flow(model, classifications, endpoint_context)
    return {"endpoint": endpoint, "steps": descriptive, "raw_flow": model, "model": model,
            "classifications": classifications, "semantic_flow": semantic_flow,
            "architecture": architecture,
            "analysis_engine": {"requested": analysis_engine,
                                "active": "spoon" if spoon_ready else "python-legacy",
                                "fallback_used": analysis_engine == "spoon-hybrid" and spoon_analysis.get("state") != "ready",
                                "flow_source": (("spoon-sootup-call-graph" if spoon_analysis.get("report", {}).get("sootup", {}).get("state") == "ready"
                                                 else "spoon-source-call-graph") if spoon_ready else "python-regex-call-graph"),
                                "spoon": spoon_analysis},
            "relations": [{"interface": k, "implementations": v} for k, v in sorted(index.items())],
            "mermaid": make_mermaid(model), "technical_mermaid": make_mermaid(model),
            "architectural_mermaid": semantic_mermaid(semantic_flow)}


def _alias(pid: str) -> str: return "P_" + re.sub(r"\W", "_", pid)


def make_mermaid(model: dict) -> str:
    lines = ["sequenceDiagram", "    autonumber"]
    for p in model["participants"]:
        keyword = "actor" if p["type"] == "actor" else "participant"; alias = _alias(p["id"])
        lines.append(f"    {keyword} {alias} as {p['display']}")
        if p.get("contracts"): lines.append(f"    Note over {alias}: implements {', '.join(p['contracts'])}")
    first, last = _alias(model["participants"][0]["id"]), _alias(model["participants"][-1]["id"])
    lines.append(f"    Note over {first},{last}: sd {model['interaction']}")
    open_fragment = None
    for event in model["events"]:
        fragment = event.get("fragment")
        same_group = fragment and open_fragment and fragment.get("group_id") == open_fragment.get("group_id")
        if same_group and fragment.get("branch") == "else" and open_fragment.get("branch") != "else":
            lines.append("    else")
            open_fragment = fragment
        elif fragment != open_fragment:
            if open_fragment: lines.append("    end")
            if fragment: lines.append(f"    {fragment['operator']} {fragment['condition']}")
            open_fragment = fragment
        if event["type"] == "call":
            lines.append(f"    {_alias(event['caller'])}->>+{_alias(event['callee'])}: {event['signature']}")
        elif event["type"] == "exception":
            lines.append(f"    {_alias(event['from'])}--x{_alias(event['to'])}: {event['exception']}")
        else:
            lines.append(f"    {_alias(event['from'])}-->>-{_alias(event['to'])}: {event['value']}")
    if open_fragment: lines.append("    end")
    return "\n".join(lines)
