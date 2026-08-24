package local.expertcodeflow;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.code.CtInvocation;
import spoon.reflect.code.CtExecutableReferenceExpression;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;
import spoon.reflect.reference.CtExecutableReference;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class SpoonAnalyzer {
    private SpoonAnalyzer() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("usage: java -jar expert-code-flow-spoon.jar <project> <output.json>");
            System.exit(2);
        }
        Path project = Path.of(args[0]).toAbsolutePath().normalize();
        Path output = Path.of(args[1]).toAbsolutePath().normalize();
        if (!Files.isDirectory(project)) throw new IllegalArgumentException("project is not a directory: " + project);

        Launcher launcher = new Launcher();
        launcher.addInputResource(project.toString());
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setComplianceLevel(17);
        launcher.getEnvironment().setCommentEnabled(false);
        launcher.buildModel();
        CtModel model = launcher.getModel();

        List<Map<String, Object>> types = new ArrayList<>();
        List<Map<String, Object>> calls = new ArrayList<>();
        model.getAllTypes().stream()
                .filter(type -> type.isTopLevel())
                .sorted(Comparator.comparing(CtType::getQualifiedName))
                .forEach(type -> collectType(project, type, types, calls));

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("schema_version", "1.0");
        report.put("engine", "spoon-sootup");
        report.put("generated_at", Instant.now().toString());
        report.put("project", project.toString());
        report.put("type_count", types.size());
        report.put("call_count", calls.size());
        report.put("types", types);
        report.put("calls", calls);
        report.put("sootup", SootUpAnalyzer.analyze(project));
        Files.createDirectories(output.getParent());
        new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT).writeValue(output.toFile(), report);
    }

    private static void collectType(Path project, CtType<?> type, List<Map<String, Object>> types,
                                    List<Map<String, Object>> calls) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("qualified_name", type.getQualifiedName());
        item.put("simple_name", type.getSimpleName());
        item.put("kind", type.isInterface() ? "interface" : type.isEnum() ? "enum" : "class");
        item.put("interfaces", type.getSuperInterfaces().stream().map(Object::toString).sorted().toList());
        item.put("superclass", type.getSuperclass() == null ? null : type.getSuperclass().getQualifiedName());
        item.put("annotations", type.getAnnotations().stream().map(a -> a.getAnnotationType().getQualifiedName()).sorted().toList());
        item.put("fields", type.getFields().stream().map(field -> {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("name", field.getSimpleName());
            value.put("type", field.getType() == null ? null : field.getType().getQualifiedName());
            value.put("annotations", field.getAnnotations().stream()
                    .map(a -> a.getAnnotationType().getQualifiedName()).sorted().toList());
            return value;
        }).toList());
        item.put("methods", type.getMethods().stream().map(method -> {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("name", method.getSimpleName());
            value.put("return_type", method.getType() == null ? null : method.getType().getQualifiedName());
            value.put("parameters", method.getParameters().stream().map(parameter -> {
                Map<String, Object> parameterValue = new LinkedHashMap<>();
                parameterValue.put("name", parameter.getSimpleName());
                parameterValue.put("type", parameter.getType() == null ? null : parameter.getType().getQualifiedName());
                parameterValue.put("annotations", parameter.getAnnotations().stream()
                        .map(a -> a.getAnnotationType().getSimpleName()).sorted().toList());
                return parameterValue;
            }).toList());
            value.put("annotations", method.getAnnotations().stream()
                    .map(a -> a.getAnnotationType().getQualifiedName()).sorted().toList());
            return value;
        }).toList());
        item.put("file", sourcePath(project, type));
        item.put("line", type.getPosition().isValidPosition() ? type.getPosition().getLine() : 0);
        types.add(item);

        type.getMethods().stream().sorted(Comparator.comparing(CtMethod::getSimpleName)).forEach(method -> {
            List<CtElement> flowElements = method.getElements(e ->
                    e instanceof CtInvocation<?> || e instanceof CtExecutableReferenceExpression<?, ?>);
            flowElements.stream()
                    .sorted(Comparator.comparingInt(e -> e.getPosition().isValidPosition()
                            ? e.getPosition().getSourceStart() : 0))
                    .forEach(element -> {
                        if (element instanceof CtInvocation<?> invocation) {
                            calls.add(call(project, type, method, invocation));
                        } else if (element instanceof CtExecutableReferenceExpression<?, ?> reference) {
                            calls.add(methodReferenceCall(project, type, method, reference));
                        }
                    });
        });
    }

    private static Map<String, Object> call(Path project, CtType<?> owner, CtMethod<?> method,
                                            CtInvocation<?> invocation) {
        CtExecutableReference<?> executable = invocation.getExecutable();
        Map<String, Object> call = new LinkedHashMap<>();
        call.put("caller_type", owner.getQualifiedName());
        call.put("caller_method", method.getSimpleName());
        call.put("method_return_type", method.getType() == null ? null : method.getType().toString());
        call.put("method_parameters", method.getParameters().stream().map(parameter -> {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("name", parameter.getSimpleName());
            value.put("type", parameter.getType() == null ? null : parameter.getType().toString());
            value.put("annotations", parameter.getAnnotations().stream()
                    .map(a -> a.getAnnotationType().getSimpleName()).sorted().toList());
            return value;
        }).toList());
        call.put("callee_type", executable.getDeclaringType() == null ? null : executable.getDeclaringType().getQualifiedName());
        call.put("target", invocation.getTarget() == null ? null : invocation.getTarget().toString());
        call.put("receiver_type", invocation.getTarget() == null || invocation.getTarget().getType() == null
                ? null : invocation.getTarget().getType().getQualifiedName());
        call.put("callee_method", executable.getSimpleName());
        call.put("signature", executable.getSignature());
        call.put("arguments", invocation.getArguments().stream().map(Object::toString).toList());
        call.put("argument_details", invocation.getArguments().stream().map(argument -> {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("expression", argument.toString());
            value.put("name", argument.getClass().getSimpleName().contains("Variable") ? argument.toString() : null);
            value.put("type", argument.getType() == null ? null : argument.getType().toString());
            return value;
        }).toList());
        call.put("call_return_type", executable.getType() == null ? null : executable.getType().toString());
        call.put("file", sourcePath(project, invocation));
        call.put("line", invocation.getPosition().isValidPosition() ? invocation.getPosition().getLine() : 0);
        call.put("resolution", executable.getDeclaringType() == null ? "UNRESOLVED" : "SPOON_TYPE_REFERENCE");
        call.put("evidence_source", "source");
        return call;
    }

    private static Map<String, Object> methodReferenceCall(Path project, CtType<?> owner, CtMethod<?> method,
                                                            CtExecutableReferenceExpression<?, ?> reference) {
        CtExecutableReference<?> executable = reference.getExecutable();
        Map<String, Object> call = new LinkedHashMap<>();
        call.put("caller_type", owner.getQualifiedName());
        call.put("caller_method", method.getSimpleName());
        call.put("callee_type", executable.getDeclaringType() == null ? null : executable.getDeclaringType().getQualifiedName());
        call.put("target", reference.getTarget() == null ? null : reference.getTarget().toString());
        call.put("receiver_type", executable.getDeclaringType() == null ? null : executable.getDeclaringType().getQualifiedName());
        call.put("callee_method", executable.getSimpleName());
        call.put("signature", executable.getSignature());
        call.put("arguments", List.of("resultado"));
        call.put("file", sourcePath(project, reference));
        call.put("line", reference.getPosition().isValidPosition() ? reference.getPosition().getLine() : 0);
        call.put("resolution", executable.getDeclaringType() == null ? "UNRESOLVED" : "SPOON_METHOD_REFERENCE");
        call.put("evidence_source", "source");
        return call;
    }

    private static String sourcePath(Path project, spoon.reflect.declaration.CtElement element) {
        if (!element.getPosition().isValidPosition() || element.getPosition().getFile() == null) return "";
        Path file = element.getPosition().getFile().toPath().toAbsolutePath().normalize();
        try { return project.relativize(file).toString(); }
        catch (IllegalArgumentException ignored) { return file.toString(); }
    }
}
