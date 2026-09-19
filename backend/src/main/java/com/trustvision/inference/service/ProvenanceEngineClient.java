package com.trustvision.inference.service;

import com.trustvision.inference.exception.VerificationRejectedException;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.exception.AiEngineException;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.nio.file.Path;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Client for the FastAPI Provenance Engine (provenance-engine/):
 * record creation and verification of hash-chained inference records.
 */
@Service
public class ProvenanceEngineClient {

    private final RestClient restClient;
    private final AppProperties properties;

    public ProvenanceEngineClient(RestClient.Builder builder, AppProperties properties) {
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) Duration.ofSeconds(5).toMillis());
        factory.setReadTimeout((int) Duration.ofSeconds(60).toMillis());
        this.restClient = builder
                .baseUrl(properties.provenanceEngine().baseUrl())
                .requestFactory(factory)
                .build();
        this.properties = properties;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> createRecord(Path imagePath, Path modelPath, Path outputPath,
                                            Map<String, Object> config, String nonce) {
        Map<String, Object> body = new HashMap<>();
        body.put("image_path", imagePath.toString());
        body.put("model_path", modelPath.toString());
        if (outputPath != null) {
            body.put("output_path", outputPath.toString());
        }
        if (config != null && !config.isEmpty()) {
            body.put("config", config);
        }
        if (nonce != null && !nonce.isBlank()) {
            body.put("nonce", nonce);
        }
        try {
            return restClient.post()
                    .uri("/api/v1/provenance/records")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(Map.class);
        } catch (RestClientResponseException e) {
            if (e.getStatusCode().value() == 409) {
                throw new VerificationRejectedException(
                        "replay detected: " + e.getResponseBodyAsString());
            }
            throw new AiEngineException("provenance engine rejected record creation: "
                    + e.getResponseBodyAsString(), e);
        } catch (RestClientException e) {
            throw new AiEngineException("could not reach the provenance engine: " + e.getMessage(), e);
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> verify(String recordId) {
        Map<String, Object> body = new HashMap<>();
        body.put("record_id", recordId);
        try {
            return restClient.post()
                    .uri("/api/v1/provenance/verify")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(Map.class);
        } catch (RestClientResponseException e) {
            throw new AiEngineException("provenance verification failed: "
                    + e.getResponseBodyAsString(), e);
        } catch (RestClientException e) {
            throw new AiEngineException("could not reach the provenance engine: " + e.getMessage(), e);
        }
    }
}
