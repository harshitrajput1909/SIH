package com.trustvision.dataset.exception;

/** Thrown for semantically invalid dataset operations. Mapped to HTTP 422. */
public class InvalidDatasetException extends RuntimeException {

    public InvalidDatasetException(String message) {
        super(message);
    }
}
