// Shared helper that connects camera/upload buttons to the image textarea fields.
document.addEventListener("DOMContentLoaded", () => {
  let cameraModal = null;
  let cameraVideo = null;
  let cameraStatus = null;
  let captureButton = null;
  let closeButton = null;
  let activeStream = null;
  let activeUpload = null;

  const stopCamera = () => {
    if (!activeStream) return;
    activeStream.getTracks().forEach((track) => track.stop());
    activeStream = null;
  };

  const closeCameraModal = () => {
    if (!cameraModal) return;
    cameraModal.hidden = true;
    activeUpload = null;
    stopCamera();
  };

  const ensureCameraModal = () => {
    if (cameraModal) return;

    cameraModal = document.createElement("div");
    cameraModal.className = "camera-modal";
    cameraModal.hidden = true;
    cameraModal.innerHTML = `
      <div class="camera-dialog">
        <h3>Take Photo</h3>
        <p class="muted camera-copy">Allow camera access, frame the image, then capture it.</p>
        <video class="camera-video" autoplay playsinline muted></video>
        <p class="muted small image-status" data-camera-status>Starting camera...</p>
        <div class="actions camera-actions">
          <button class="btn" type="button" data-camera-capture>Capture Photo</button>
          <button class="btn ghost" type="button" data-camera-close>Cancel</button>
        </div>
      </div>
    `;
    document.body.appendChild(cameraModal);

    cameraVideo = cameraModal.querySelector(".camera-video");
    cameraStatus = cameraModal.querySelector("[data-camera-status]");
    captureButton = cameraModal.querySelector("[data-camera-capture]");
    closeButton = cameraModal.querySelector("[data-camera-close]");

    closeButton.addEventListener("click", closeCameraModal);

    cameraModal.addEventListener("click", (event) => {
      if (event.target === cameraModal) {
        closeCameraModal();
      }
    });

    captureButton.addEventListener("click", async () => {
      if (!cameraVideo || !activeUpload) return;
      const canvas = document.createElement("canvas");
      canvas.width = cameraVideo.videoWidth || 1280;
      canvas.height = cameraVideo.videoHeight || 720;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(async (blob) => {
        if (!blob || !activeUpload) return;
        const file = new File([blob], `camera_${Date.now()}.jpg`, { type: "image/jpeg" });
        await activeUpload([file]);
        closeCameraModal();
      }, "image/jpeg", 0.92);
    });
  };

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
      } finally {
        cameraInput.value = "";
        uploadInput.value = "";
      }
    };

    const openDesktopCamera = async () => {
      ensureCameraModal();
      if (!cameraModal || !cameraVideo || !cameraStatus) return false;

      try {
        activeUpload = uploadFiles;
        cameraStatus.textContent = "Starting camera...";
        cameraModal.hidden = false;
        activeStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
          audio: false,
        });
        cameraVideo.srcObject = activeStream;
        cameraStatus.textContent = "Camera ready.";
        return true;
      } catch (error) {
        console.error("Camera access failed", error);
        closeCameraModal();
        return false;
      }
    };

    cameraButton.addEventListener("click", async () => {
      if (navigator.mediaDevices?.getUserMedia) {
        const opened = await openDesktopCamera();
        if (opened) return;
      }
      cameraInput.click();
    });
    uploadButton.addEventListener("click", () => uploadInput.click());
    cameraInput.addEventListener("change", () => uploadFiles(cameraInput.files));
    uploadInput.addEventListener("change", () => uploadFiles(uploadInput.files));
  });
});
