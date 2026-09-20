package com.trustvision.dataset.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.nio.file.Path;
import java.time.Duration;

@ConfigurationProperties(prefix = "app")
public record AppProperties(Storage storage, String ownerUsername, AiEngine aiEngine,
                            ProvenanceEngine provenanceEngine) {

    public AppProperties {
        if (storage == null) {
            storage = new Storage(Path.of("workspace/storage"));
        }
        if (ownerUsername == null || ownerUsername.isBlank()) {
            ownerUsername = System.getenv().getOrDefault("APP_OWNER_USERNAME", "system");
        }
        if (aiEngine == null) {
            aiEngine = new AiEngine(
                    System.getenv().getOrDefault("AI_ENGINE_BASE_URL", "http://localhost:8100"),
                    Duration.ofSeconds(2),
                    Duration.ofMinutes(15)
            );
        }
        if (provenanceEngine == null) {
            provenanceEngine = new ProvenanceEngine(
                    System.getenv().getOrDefault("PROVENANCE_ENGINE_BASE_URL", "http://localhost:8200")
            );
        }
    }

    public record Storage(Path root) {
        public Storage {
            if (root == null) {
                root = Path.of("workspace/storage");
            }
        }
    }

    public record AiEngine(String baseUrl, Duration pollInterval, Duration timeout) {
        public AiEngine {
            if (baseUrl == null || baseUrl.isBlank()) {
                baseUrl = "http://localhost:8100";
            }
            if (pollInterval == null || pollInterval.isNegative() || pollInterval.isZero()) {
                pollInterval = Duration.ofSeconds(2);
            }
            if (timeout == null || timeout.isNegative() || timeout.isZero()) {
                timeout = Duration.ofMinutes(15);
            }
        }
    }

    public record ProvenanceEngine(String baseUrl) {
        public ProvenanceEngine {
            if (baseUrl == null || baseUrl.isBlank()) {
                baseUrl = "http://localhost:8200";
            }
        }
    }
}
