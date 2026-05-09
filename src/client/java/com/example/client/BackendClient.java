package com.example.client;

import com.example.network.BuildBlockEntry;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

final class BackendClient {

    private static final Gson   GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    private static final String DEFAULT_BASE_URL = "http://127.0.0.1:8000";

    private static final ScheduledExecutorService POLL_EXEC =
            Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "architect-poll");
                t.setDaemon(true);
                return t;
            });

    private BackendClient() {}

    record StageUpdate(String stage, float progress) {}

    private record GenerateBody(String prompt, int[] max_size) {}

    // -------------------------------------------------------------------------
    // Public API

    static CompletableFuture<List<BuildBlockEntry>> generateBlocks(
            String prompt, int[] maxSize, Consumer<StageUpdate> onProgress) {

        CompletableFuture<List<BuildBlockEntry>> result = new CompletableFuture<>();

        startJob(prompt, maxSize).whenComplete((jobId, err) -> {
            if (err != null) { result.completeExceptionally(unwrap(err)); return; }
            schedulePoll(jobId, result, onProgress);
        });

        return result;
    }

    // -------------------------------------------------------------------------
    // Step 1: POST /generate → job_id

    private static CompletableFuture<String> startJob(String prompt, int[] maxSize) {
        String body = GSON.toJson(new GenerateBody(prompt, maxSize));
        HttpRequest req = HttpRequest.newBuilder(uri("/generate"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        return HTTP.sendAsync(req, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> {
                    if (response.statusCode() < 200 || response.statusCode() >= 300)
                        throw new CompletionException(new IOException(readErrorMessage(response)));
                    try {
                        JsonObject obj = GSON.fromJson(response.body(), JsonObject.class);
                        return obj.get("job_id").getAsString();
                    } catch (JsonParseException | NullPointerException exc) {
                        throw new CompletionException(new IOException("Malformed start response", exc));
                    }
                });
    }

    // -------------------------------------------------------------------------
    // Step 2: GET /generate/{jobId} — poll every 2 s

    private static void schedulePoll(String jobId,
                                     CompletableFuture<List<BuildBlockEntry>> result,
                                     Consumer<StageUpdate> onProgress) {
        POLL_EXEC.schedule(() -> {
            pollOnce(jobId).whenComplete((poll, err) -> {
                if (err != null) { result.completeExceptionally(unwrap(err)); return; }
                if (poll.error != null) {
                    result.completeExceptionally(new IOException(poll.error));
                    return;
                }
                if (onProgress != null)
                    onProgress.accept(new StageUpdate(poll.stage, poll.progress));
                if (poll.done) {
                    result.complete(poll.blocks);
                } else {
                    schedulePoll(jobId, result, onProgress);
                }
            });
        }, 2, TimeUnit.SECONDS);
    }

    private static CompletableFuture<PollResult> pollOnce(String jobId) {
        HttpRequest req = HttpRequest.newBuilder(uri("/generate/" + jobId)).GET().build();
        return HTTP.sendAsync(req, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> {
                    if (response.statusCode() < 200 || response.statusCode() >= 300)
                        throw new CompletionException(new IOException(readErrorMessage(response)));
                    try {
                        JsonObject obj = GSON.fromJson(response.body(), JsonObject.class);
                        boolean done      = obj.get("done").getAsBoolean();
                        String  stage     = obj.has("stage") ? obj.get("stage").getAsString() : "";
                        float   progress  = obj.has("progress") ? obj.get("progress").getAsFloat() : 0f;
                        String  error     = obj.has("error") && !obj.get("error").isJsonNull()
                                            ? obj.get("error").getAsString() : null;
                        List<BuildBlockEntry> blocks = null;
                        if (done && obj.has("blocks") && !obj.get("blocks").isJsonNull()) {
                            try {
                                blocks = parseBlocks(obj.getAsJsonArray("blocks"));
                            } catch (IOException exc) {
                                throw new CompletionException(exc);
                            }
                        }
                        return new PollResult(done, stage, progress, error, blocks);
                    } catch (JsonParseException exc) {
                        throw new CompletionException(exc);
                    }
                });
    }

    private static List<BuildBlockEntry> parseBlocks(JsonArray arr) throws IOException {
        List<BuildBlockEntry> list = new ArrayList<>(arr.size());
        for (JsonElement el : arr) {
            JsonObject o = el.getAsJsonObject();
            list.add(new BuildBlockEntry(
                    o.get("x").getAsInt(),
                    o.get("y").getAsInt(),
                    o.get("z").getAsInt(),
                    o.get("block").getAsString()
            ));
        }
        return list;
    }

    // -------------------------------------------------------------------------
    // Helpers

    private static URI uri(String path) {
        String configured = System.getProperty("modid.backendUrl");
        if (configured == null || configured.isBlank())
            configured = System.getenv("MINECRAFT_AI_BACKEND_URL");
        String base = (configured == null || configured.isBlank()) ? DEFAULT_BASE_URL : configured.trim();
        return URI.create(base.replaceAll("/+$", "") + path);
    }

    private static String readErrorMessage(HttpResponse<String> response) {
        try {
            JsonObject json = GSON.fromJson(response.body(), JsonObject.class);
            if (json != null && json.has("detail"))
                return "Backend error: " + json.get("detail").getAsString();
        } catch (Exception ignored) {}
        return "Backend error: HTTP " + response.statusCode();
    }

    private static Throwable unwrap(Throwable t) {
        return (t instanceof CompletionException && t.getCause() != null) ? t.getCause() : t;
    }

    private record PollResult(boolean done, String stage, float progress,
                               String error, List<BuildBlockEntry> blocks) {}
}
