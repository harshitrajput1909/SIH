package com.trustvision.dataset.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;
import java.util.List;

@Configuration
public class CorsConfig {

    @Bean
    public WebMvcConfigurer corsConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                String configuredOrigins = System.getenv().getOrDefault(
                        "CORS_ALLOWED_ORIGINS",
                        "http://localhost:5173,http://localhost:3000,https://YOUR_FRONTEND_DOMAIN"
                );

                List<String> origins = Arrays.stream(configuredOrigins.split(","))
                        .map(String::trim)
                        .filter(value -> !value.isEmpty())
                        .toList();

                registry.addMapping("/**")
                        .allowedOrigins(origins.toArray(String[]::new))
                        .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                        .allowedHeaders("*")
                        .allowCredentials(true);
            }
        };
    }
}
