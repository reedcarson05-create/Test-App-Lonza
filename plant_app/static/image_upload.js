// Shared helper that connects camera/upload buttons to the image textarea fields.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-image-field-container]").forEach((container) => {
    const textarea = container.querySelector("[data-image-field]");
    const cameraInput = container.querySelector("[data-image-camera-input]");
    const uploadInput = container.querySelector("[data-image-upload-input]");
    const cameraButton = container.querySelector("[data-image-camera-button]");
    const uploadButton = container.querySelector("[data-image-upload-button]");
    const status = container.querySelector("[data-image-status]");
    const endpoint = container.dataset.uploadEndpoint || "/upload-image";

    if (!textarea || !cameraInput || !uploadInput || !cameraButton || !uploadButton || !status) return;

    const setStatus = (message) => {
      status.textContent = message;
    };

    const appendUrls = (urls) => {
      const existing = textarea.value.trim();
      const nextValue = [existing, ...urls].filter(Boolean).join("\n");
      textarea.value = nextValue;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    };

    const uploadFiles = async (fileList) => {
      const files = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
      if (!files.length) {
        setStatus("No image selected yet.");
        return;
      }

      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      setStatus(files.length === 1 ? "Uploading image..." : `Uploading ${files.length} images...`);

      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body: formData,
        });
        const payload = await response.json();
        if (!response.ok) {
          setStatus(payload.error || "Image upload failed.");
          return;
        }

        const urls = (payload.files || []).map((file) => file.url).filter(Boolean);
        appendUrls(urls);
        setStatus(urls.length === 1 ? "Image added." : `${urls.length} images added.`);
      } catch (error) {
        console.error("Image upload failed", error);
        setStatus("Image upload failed.");
      }
    };

    cameraButton.addEventListener("click", () => cameraInput.click());
    uploadButton.addEventListener("click", () => uploadInput.click());
    cameraInput.addEventListener("change", () => uploadFiles(cameraInput.files));
    uploadInput.addEventListener("change", () => uploadFiles(uploadInput.files));
  });
});
