package com.trustvision.inference.exception;

/** Thrown when the provenance engine rejects a request (e.g. nonce replay). Mapped to HTTP 409. */
public class VerificationRejectedException extends RuntimeException {

    public VerificationRejectedException(String message) {
        super(message);
    }
}
