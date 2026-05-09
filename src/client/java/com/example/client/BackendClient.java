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
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;

final class BackendClient {

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    private static final String DEFAULT_BASE_URL = "http://127.0.0.1:8000";

    private BackendClient() {}

    static CompletableFuture<List<BuildBlockEntry>> generateBlocks(String prompt) {
        HttpRequest request = HttpRequest.newBuilder(generateUri())
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(Map.of("prompt", prompt))))
                .build();

        return HTTP.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> {
                    if (response.statusCode() < 200 || response.statusCode() >= 300) {
                        throw new CompletionException(new IOException(readErrorMessage(response)));
                    }
                    try {
                        JsonArray arr = GSON.fromJson(response.body(), JsonArray.class);
                        if (arr == null) throw new IOException("Backend returned an empty response");
                        List<BuildBlockEntry> blocks = new ArrayList<>(arr.size());
                        for (JsonElement el : arr) {
                            JsonObject o = el.getAsJsonObject();
                            blocks.add(new BuildBlockEntry(
                                    o.get("x").getAsInt(),
                                    o.get("y").getAsInt(),
                                    o.get("z").getAsInt(),
                                    o.get("block").getAsString()
                            ));
                        }
                        return blocks;
                    } catch (JsonParseException | IOException exc) {
                        throw new CompletionException(exc);
                    }
                });
    }

    private static URI generateUri() {
        String configured = System.getProperty("modid.backendUrl");
        if (configured == null || configured.isBlank()) {
            configured = System.getenv("MINECRAFT_AI_BACKEND_URL");
        }
        String baseUrl = (configured == null || configured.isBlank()) ? DEFAULT_BASE_URL : configured.trim();
        return URI.create(baseUrl.replaceAll("/+$", "") + "/generate");
    }

    private static String readErrorMessage(HttpResponse<String> response) {
        try {
            JsonObject json = GSON.fromJson(response.body(), JsonObject.class);
            if (json != null && json.has("detail")) {
                return "Backend error: " + json.get("detail").getAsString();
            }
        } catch (Exception ignored) {
            // Fall back to the raw status line below.
        }
        return "Backend error: HTTP " + response.statusCode();
    }
}
