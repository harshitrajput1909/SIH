package com.trustvision.dataset.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiAssuranceResult;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiJobAccepted;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiJobStatus;
import com.trustvision.dataset.exception.AiEngineException;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Client for the FastAPI Dataset Assurance Engine (ai-engine/).
 * Submits an analysis job, then polls until COMPLETED / FAILED / timeout.
 */
@Service
public class AiEngineClient {

    private final RestClient restClient;
    private final AppProperties properties;

    public AiEngineClient(RestClient.Builder builder, AppProperties properties, ObjectMapper objectMapper) {
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) Duration.ofSeconds(5).toMillis());
        factory.setReadTimeout((int) Duration.ofSeconds(60).toMillis());
        this.restClient = builder
                .baseUrl(properties.aiEngine().baseUrl())
                .requestFactory(factory)
                .build();
        this.properties = properties;
    }

    public String submitJob(Path sourcePath, String datasetFormat, Map<String, Object> options) {
        Map<String, Object> body = new HashMap<>();
        body.put("source_path", sourcePath.toString());
        body.put("dataset_format", datasetFormat);
        if (options != null && !options.isEmpty()) {
            body.put("options", options);
        }
        try {
            AiJobAccepted accepted = restClient.post()
                    .uri("/api/v1/analyses")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(AiJobAccepted.class);
            if (accepted == null || accepted.jobId() == null) {
                throw new AiEngineException("engine accepted the job but returned no job id");
            }
            return accepted.jobId();
        } catch (RestClientException e) {
            throw new AiEngineException("could not submit analysis job to the AI engine: " + e.getMessage(), e);
        }
    }

    public AiAssuranceResult awaitResult(String jobId) {
        Instant deadline = Instant.now().plus(properties.aiEngine().timeout());
        while (Instant.now().isBefore(deadline)) {
            AiJobStatus status;
            try {
                status = restClient.get()
                        .uri("/api/v1/analyses/{id}", jobId)
                        .retrieve()
                        .body(AiJobStatus.class);
            } catch (RestClientException e) {
                throw new AiEngineException("lost contact with the AI engine while polling: " + e.getMessage(), e);
            }
            if (status == null) {
                throw new AiEngineException("engine returned an empty status response");
            }
            switch (status.status() == null ? "" : status.status()) {
                case "COMPLETED" -> {
                    if (status.result() == null) {
                        throw new AiEngineException("engine reported COMPLETED without a result");
                    }
                    return status.result();
                }
                case "FAILED" -> throw new AiEngineException(
                        "engine analysis failed: " + String.valueOf(status.error()));
                case "CANCELLED" -> throw new AiEngineException("engine analysis was cancelled");
                default -> {
                    // still QUEUED / RUNNING — keep polling
                }
            }
            try {
                Thread.sleep(properties.aiEngine().pollInterval().toMillis());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new AiEngineException("polling interrupted while waiting for engine job " + jobId);
            }
        }
        throw new AiEngineException("timed out waiting for engine job " + jobId
                + " after " + properties.aiEngine().timeout());
    }
}
