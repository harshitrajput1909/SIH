package com.trustvision.dataset.exception;

/** Thrown when the AI engine is unreachable, fails, or times out. Mapped to HTTP 502. */
public class AiEngineException extends RuntimeException {

    public AiEngineException(String message) {
        super(message);
    }

    public AiEngineException(String message, Throwable cause) {
        super(message, cause);
    }
}
