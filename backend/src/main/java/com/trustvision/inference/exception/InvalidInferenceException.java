package com.trustvision.inference.exception;

/** Thrown for semantically invalid inference verification requests. Mapped to HTTP 422. */
public class InvalidInferenceException extends RuntimeException {

    public InvalidInferenceException(String message) {
        super(message);
    }
}
