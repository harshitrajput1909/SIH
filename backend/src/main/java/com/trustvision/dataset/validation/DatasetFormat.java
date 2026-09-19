package com.trustvision.dataset.validation;

import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.util.Set;

/**
 * Validates that a dataset format string is one of the supported values
 * (COCO / YOLO), case-insensitive.
 */
@Documented
@Constraint(validatedBy = DatasetFormat.DatasetFormatValidator.class)
@Target({ElementType.PARAMETER, ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
public @interface DatasetFormat {

    String message() default "format must be one of: COCO, YOLO";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};

    class DatasetFormatValidator implements ConstraintValidator<DatasetFormat, String> {

        private static final Set<String> ALLOWED = Set.of("COCO", "YOLO");

        @Override
        public boolean isValid(String value, ConstraintValidatorContext context) {
            if (value == null || value.isBlank()) {
                return false;
            }
            return ALLOWED.contains(value.trim().toUpperCase());
        }
    }
}
