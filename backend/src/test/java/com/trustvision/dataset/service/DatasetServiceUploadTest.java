package com.trustvision.dataset.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.domain.Dataset;
import com.trustvision.dataset.domain.User;
import com.trustvision.dataset.dto.response.DatasetResponse;
import com.trustvision.dataset.repository.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.PlatformTransactionManager;

import java.nio.file.Path;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DatasetServiceUploadTest {

    @Mock
    private DatasetRepository datasetRepository;
    @Mock
    private DatasetAnalysisRepository analysisRepository;
    @Mock
    private ContributorRepository contributorRepository;
    @Mock
    private ContributorRiskRepository contributorRiskRepository;
    @Mock
    private DatasetEvidenceRepository evidenceRepository;
    @Mock
    private UserRepository userRepository;
    @Mock
    private StorageService storageService;
    @Mock
    private AiEngineClient aiEngineClient;
    @Mock
    private PlatformTransactionManager transactionManager;

    @Test
    void uploadPersistsDatasetOnlyAfterStorageMetadataIsReady() throws Exception {
        User owner = new User();
        ReflectionTestUtils.setField(owner, "id", UUID.fromString("00000000-0000-0000-0000-000000000001"));
        owner.setUsername("system");
        owner.setFullName("System");

        AppProperties properties = new AppProperties(
                new AppProperties.Storage(Path.of("target/test-storage")),
                "system",
                new AppProperties.AiEngine("http://localhost:8100", Duration.ofSeconds(2), Duration.ofMinutes(1)),
                new AppProperties.ProvenanceEngine("http://localhost:8200")
        );

        when(userRepository.findByUsername("system")).thenReturn(Optional.of(owner));
        when(storageService.storeDatasetArtefact(any(UUID.class), any()))
                .thenReturn(new StorageService.StoredFile("/tmp/sample.zip", 2048L, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"));
        when(datasetRepository.save(any(Dataset.class))).thenAnswer(invocation -> invocation.getArgument(0));

        DatasetService service = new DatasetService(
                datasetRepository,
                analysisRepository,
                contributorRepository,
                contributorRiskRepository,
                evidenceRepository,
                userRepository,
                storageService,
                aiEngineClient,
                new ObjectMapper(),
                transactionManager,
                properties
        );

        MockMultipartFile file = new MockMultipartFile(
                "file",
                "sample.zip",
                "application/zip",
                new byte[] {1, 2, 3, 4}
        );

        DatasetResponse response = service.upload(file, "Alpha", "alpha", "COCO", "OFFICIAL", "notes");

        InOrder inOrder = inOrder(storageService, datasetRepository);
        inOrder.verify(storageService).storeDatasetArtefact(any(UUID.class), eq(file));
        inOrder.verify(datasetRepository).save(any(Dataset.class));

        assertEquals("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", response.sha256());
        assertEquals(2048L, response.sizeBytes());
        assertEquals("Alpha", response.name());
    }
}
