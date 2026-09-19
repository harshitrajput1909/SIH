package com.trustvision.inference.service;

import com.trustvision.dataset.service.StorageService;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;

/** Thin adapter so the inference module never touches storage internals directly. */
@Component
public class InferenceArtifactStore {

    private final StorageService delegate;

    public InferenceArtifactStore(StorageService delegate) {
        this.delegate = delegate;
    }

    public StorageService.StoredFile store(UUID requestId, String slot, MultipartFile file) throws IOException {
        return delegate.storeInferenceArtifact(requestId, slot, file);
    }
}
