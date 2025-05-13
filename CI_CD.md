# CI/CD for Audio Converter

This document explains the Continuous Integration and Continuous Delivery setup for the WAV Maker application.

## Overview

The CI/CD pipeline is implemented using GitHub Actions and focuses on:

1. Running tests to ensure code quality
2. Building Docker images
3. Publishing images to GitHub Container Registry (GHCR)
4. Creating GitHub releases for tagged versions

## Workflow

The `.github/workflows/build-and-publish.yml` file defines the automated workflow:

### Triggers

The workflow runs on:
- Pushes to the `main` branch
- New version tags (`v*` format)
- Pull requests to the `main` branch
- Manual triggering via GitHub UI

### Jobs

#### 1. Test

- Runs Python linting with flake8
- Executes unit tests with pytest
- Generates code coverage reports
- Uploads coverage data to Codecov (if configured)

#### 2. Build and Publish

- Builds a Docker image using the project's Dockerfile
- Tags the image according to the context:
  - For main branch: `latest` and `sha-{commit-hash}`
  - For tags: semantic version tags like `v1.0.0`, `v1.0`, `v1`
- Pushes the image to GitHub Container Registry
- Uses layer caching to speed up builds

#### 3. Notify Release

- Runs only for version tags
- Generates a changelog from commit messages
- Creates a GitHub release with:
  - Release notes based on commits
  - Instructions for pulling the Docker image

## Using the Docker Images

The Docker images are published to GitHub Container Registry and can be pulled using:

```bash
# Latest version from main branch
docker pull ghcr.io/yourusername/audio-converter:latest

# Specific version
docker pull ghcr.io/yourusername/audio-converter:v1.0.0
```

## Releasing New Versions

To create a new release:

1. Tag your commit with a semantic version:
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

2. The workflow will automatically:
   - Run tests
   - Build and tag the Docker image
   - Push the image to GHCR
   - Create a GitHub release

## Container Image Specification

The published Docker image:
- Is based on Python 3.11
- Has FFmpeg installed for audio processing
- Runs as a non-root user for security
- Exposes port 5000
- Uses Gunicorn as the WSGI server
- Includes all necessary dependencies

## Integrating with Your Production Infrastructure

The Docker images are ready to be pulled by your production infrastructure. You can:

1. Configure your infrastructure to pull the `latest` tag for automatic updates
2. Or specify version tags for controlled, pinned deployments
3. Set up monitoring to detect when new images are published

The images are publicly accessible in the GitHub Container Registry, making them easy to integrate with various deployment platforms.

## Troubleshooting

If you encounter issues with the CI/CD pipeline:

1. Check the GitHub Actions logs for detailed error messages
2. Verify that your tests are passing locally
3. Ensure your Dockerfile is correctly configured
4. Check that the GitHub token has appropriate permissions