package local.expertcodeflow;

import sootup.callgraph.CallGraph;
import sootup.callgraph.ClassHierarchyAnalysisAlgorithm;
import sootup.core.graph.BasicBlock;
import sootup.core.graph.StmtGraph;
import sootup.core.inputlocation.AnalysisInputLocation;
import sootup.core.jimple.common.expr.AbstractInvokeExpr;
import sootup.core.jimple.common.stmt.Stmt;
import sootup.core.model.Body;
import sootup.core.model.SourceType;
import sootup.core.signatures.MethodSignature;
import sootup.core.typehierarchy.TypeHierarchy;
import sootup.java.bytecode.frontend.inputlocation.DefaultRuntimeAnalysisInputLocation;
import sootup.java.bytecode.frontend.inputlocation.JavaClassPathAnalysisInputLocation;
import sootup.java.core.JavaSootClass;
import sootup.java.core.JavaSootMethod;
import sootup.java.core.views.JavaView;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Bytecode evidence provider. All failures are represented in JSON so Spoon remains usable. */
final class SootUpAnalyzer {
    private SootUpAnalyzer() {}

    static Map<String, Object> analyze(Path project) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("engine", "sootup");
        result.put("version", "2.0.0");
        List<Path> roots = bytecodeRoots(project);
        result.put("bytecode_roots", roots.stream().map(project::relativize).map(Path::toString).toList());
        if (roots.isEmpty()) {
            result.put("state", "bytecode_unavailable");
            result.put("message", "Compile o projeto (Maven/Gradle) para habilitar Call Graph e CFG do SootUp");
            result.put("calls", List.of());
            result.put("hierarchy", List.of());
            result.put("control_flow", List.of());
            return result;
        }

        try {
            String classPath = String.join(File.pathSeparator, roots.stream().map(Path::toString).toList());
            List<AnalysisInputLocation> inputs = new ArrayList<>();
            inputs.add(new JavaClassPathAnalysisInputLocation(classPath, SourceType.Application));
            inputs.add(new DefaultRuntimeAnalysisInputLocation());
            JavaView view = new JavaView(inputs);
            List<JavaSootClass> classes = view.getClasses()
                    .filter(JavaSootClass::isApplicationClass)
                    .sorted(Comparator.comparing(c -> c.getType().getFullyQualifiedName()))
                    .toList();
            TypeHierarchy hierarchy = view.getTypeHierarchy();
            List<Map<String, Object>> hierarchyItems = new ArrayList<>();
            List<Map<String, Object>> calls = new ArrayList<>();
            List<Map<String, Object>> cfgs = new ArrayList<>();
            List<MethodSignature> entries = new ArrayList<>();

            for (JavaSootClass clazz : classes) {
                Map<String, Object> hierarchyItem = new LinkedHashMap<>();
                hierarchyItem.put("type", clazz.getType().getFullyQualifiedName());
                hierarchyItem.put("interface", clazz.isInterface());
                hierarchyItem.put("superclass", clazz.getSuperclass().map(t -> t.getFullyQualifiedName()).orElse(null));
                hierarchyItem.put("interfaces", clazz.getInterfaces().stream().map(t -> t.getFullyQualifiedName()).sorted().toList());
                hierarchyItem.put("all_interfaces", hierarchy.implementedInterfacesOf(clazz.getType())
                        .map(t -> t.getFullyQualifiedName()).sorted().toList());
                hierarchyItems.add(hierarchyItem);

                for (JavaSootMethod method : clazz.getMethods()) {
                    if (!method.isConcrete() || !method.hasBody()) continue;
                    entries.add(method.getSignature());
                    try {
                        Body body = method.getBody();
                        StmtGraph<?> graph = body.getStmtGraph();
                        int normalEdges = graph.getNodes().stream().mapToInt(s -> graph.successors(s).size()).sum();
                        int exceptionalEdges = graph.getNodes().stream().mapToInt(s -> graph.exceptionalSuccessors(s).size()).sum();
                        Map<String, Object> cfg = new LinkedHashMap<>();
                        cfg.put("method", signature(method.getSignature()));
                        cfg.put("statement_count", graph.getNodes().size());
                        cfg.put("basic_block_count", graph.getBlocks().size());
                        cfg.put("edge_count", normalEdges);
                        cfg.put("exceptional_edge_count", exceptionalEdges);
                        cfg.put("branch_count", graph.getNodes().stream().filter(Stmt::branches).count());
                        cfg.put("entry_count", graph.getEntrypoints().size());
                        cfg.put("tail_count", graph.getTails().size());
                        cfgs.add(cfg);

                        int ordinal = 0;
                        for (Stmt stmt : body.getStmts()) {
                            ordinal++;
                            if (!stmt.isInvokableStmt()) continue;
                            var expression = stmt.asInvokableStmt().getInvokeExpr();
                            if (expression.isEmpty()) continue;
                            calls.add(call(method.getSignature(), expression.get(), ordinal, stmt.toString()));
                        }
                    } catch (RuntimeException ignored) {
                        // A malformed/unresolved method body must not discard other bytecode evidence.
                    }
                }
            }

            Map<String, Object> callGraphReport = callGraph(view, entries);
            result.put("state", "ready");
            result.put("class_count", classes.size());
            result.put("method_count", entries.size());
            result.put("calls", calls);
            result.put("hierarchy", hierarchyItems);
            result.put("control_flow", cfgs);
            result.put("call_graph", callGraphReport);
        } catch (RuntimeException error) {
            result.put("state", "failed");
            result.put("message", error.getClass().getSimpleName() + ": " + error.getMessage());
            result.putIfAbsent("calls", List.of());
            result.putIfAbsent("hierarchy", List.of());
            result.putIfAbsent("control_flow", List.of());
        }
        return result;
    }

    private static Map<String, Object> callGraph(JavaView view, List<MethodSignature> entries) {
        Map<String, Object> report = new LinkedHashMap<>();
        try {
            CallGraph graph = new ClassHierarchyAnalysisAlgorithm(view).initialize(entries);
            List<Map<String, String>> edges = new ArrayList<>();
            for (MethodSignature source : graph.getMethodSignatures()) {
                for (MethodSignature target : graph.callTargetsFrom(source)) {
                    edges.add(Map.of("source", signature(source), "target", signature(target)));
                }
            }
            report.put("state", "ready");
            report.put("algorithm", "CHA");
            report.put("entry_count", graph.getEntryMethods().size());
            report.put("method_count", graph.getMethodSignatures().size());
            report.put("edge_count", graph.callCount());
            report.put("edges", edges);
        } catch (RuntimeException error) {
            report.put("state", "failed");
            report.put("algorithm", "CHA");
            report.put("message", error.getClass().getSimpleName() + ": " + error.getMessage());
            report.put("edges", List.of());
        }
        return report;
    }

    private static Map<String, Object> call(MethodSignature caller, AbstractInvokeExpr expression,
                                             int ordinal, String statement) {
        MethodSignature callee = expression.getMethodSignature();
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("caller_type", caller.getDeclClassType().getFullyQualifiedName());
        item.put("caller_method", caller.getName());
        item.put("caller_signature", signature(caller));
        item.put("callee_type", callee.getDeclClassType().getFullyQualifiedName());
        item.put("receiver_type", callee.getDeclClassType().getFullyQualifiedName());
        item.put("callee_method", callee.getName());
        item.put("callee_signature", signature(callee));
        item.put("arguments", expression.getArgs().stream().map(Object::toString).toList());
        item.put("ordinal", ordinal);
        item.put("line", 0);
        item.put("statement", statement);
        item.put("resolution", "SOOTUP_BYTECODE");
        item.put("evidence_source", "bytecode");
        return item;
    }

    private static String signature(MethodSignature signature) {
        return signature.getDeclClassType().getFullyQualifiedName() + "." + signature.getName()
                + "(" + String.join(",", signature.getParameterTypes().stream().map(Object::toString).toList()) + ")";
    }

    private static List<Path> bytecodeRoots(Path project) {
        Set<Path> roots = new LinkedHashSet<>();
        try (var paths = Files.walk(project, 8)) {
            paths.filter(Files::isDirectory).forEach(path -> {
                String normalized = path.toString().replace('\\', '/');
                if (normalized.endsWith("/target/classes") || normalized.endsWith("/build/classes/java/main")
                        || normalized.endsWith("/build/classes/kotlin/main")) roots.add(path.toAbsolutePath().normalize());
            });
        } catch (IOException ignored) { }
        return roots.stream().sorted().toList();
    }
}
