package com.trustvision.inference.controller;

import com.trustvision.inference.dto.InferenceDtos.EvidenceItemDto;
import com.trustvision.inference.dto.InferenceDtos.InferenceDetailResponse;
import com.trustvision.inference.dto.InferenceDtos.InferenceVerifyResponse;
import com.trustvision.inference.dto.InferenceDtos.ProvenanceRecordDto;
import com.trustvision.inference.service.InferenceService;
import com.trustvision.inference.exception.InvalidInferenceException;
import com.trustvision.inference.exception.VerificationRejectedException;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.http.MediaType;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/inference")
@Validated
public class InferenceController {

    private final InferenceService inferenceService;

    public InferenceController(InferenceService inferenceService) {
        this.inferenceService = inferenceService;
    }

    @PostMapping(value = "/verify", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public InferenceVerifyResponse verify(
            @RequestParam("image") MultipartFile image,
            @RequestParam("model") MultipartFile model,
            @RequestParam(value = "output", required = false) MultipartFile output,
            @RequestParam(value = "config", required = false) String configJson,
            @RequestParam(value = "nonce", required = false) @Size(max = 128) String nonce
    ) {
        return inferenceService.verify(image, model, output, configJson, nonce);
    }

    @GetMapping("/{id}")
    public InferenceDetailResponse get(@PathVariable @NotNull java.util.UUID id) {
        return inferenceService.get(id);
    }

    @GetMapping("/provenance/{id}")
    public ProvenanceRecordDto provenance(@PathVariable @NotNull java.util.UUID id) {
        return inferenceService.provenance(id);
    }

    @GetMapping("/evidence/{id}")
    public List<EvidenceItemDto> evidence(@PathVariable @NotNull java.util.UUID id) {
        return inferenceService.evidence(id);
    }
}
