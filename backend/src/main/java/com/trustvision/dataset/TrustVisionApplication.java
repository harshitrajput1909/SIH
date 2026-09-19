package com.trustvision.dataset;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class TrustVisionApplication {

    public static void main(String[] args) {
        SpringApplication.run(TrustVisionApplication.class, args);
    }
}
