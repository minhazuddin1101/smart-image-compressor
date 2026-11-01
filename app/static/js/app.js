(() => {
  let maxFiles = 10;
  let maxFileBytes = 10 * 1024 * 1024;
  let maxDimension = 12000;
  const $ = (selector) => document.querySelector(selector);
  const fileInput = $("#file-input");
  const dropZone = $("#drop-zone");
  const selection = $("#selection");
  const message = $("#upload-message");
  const compressButton = $("#compress-button");
  const progressArea = $("#progress-area");
  const resultsSection = $("#results-section");
  const resultsList = $("#results-list");
  const outputFormat = $("#output-format");
  const resizeMode = $("#resize-mode");
  const dimensionFields = $("#dimension-fields");
  const quality = $("#quality");
  const items = [];
  const results = [];
  let busy = false;

  function getSessionId() {
    let id = localStorage.getItem("sic-session-id");
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(24)), (n) => n.toString(16).padStart(2, "0")).join("");
      localStorage.setItem("sic-session-id", id);
    }
    return id;
  }
  const sessionId = getSessionId();

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB"];
    let value = bytes / 1024;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit++;
    }
    return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unit]}`;
  }

  function showMessage(element, text, isError = false) {
    element.textContent = text;
    element.classList.toggle("error", isError);
  }

  function renderSelection() {
    selection.replaceChildren();
    items.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "file-row";
      const image = document.createElement("img");
      image.className = "file-thumb";
      image.src = item.url;
      image.alt = "";
      const info = document.createElement("div");
      info.className = "file-info";
      const name = document.createElement("div");
      name.className = "file-name";
      name.textContent = item.file.name;
      const size = document.createElement("div");
      size.className = "file-size";
      size.textContent = formatBytes(item.file.size);
      info.append(name, size);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-file";
      remove.setAttribute("aria-label", `Remove ${item.file.name}`);
      remove.textContent = "×";
      remove.disabled = busy;
      remove.addEventListener("click", () => removeItem(index));
      row.append(image, info, remove);
      selection.append(row);
    });
    compressButton.disabled = busy || items.length === 0;
    $("#clear-selection").disabled = busy || items.length === 0;
  }

  function removeItem(index) {
    URL.revokeObjectURL(items[index].url);
    items.splice(index, 1);
    renderSelection();
    showMessage(message, "");
  }

  function addFiles(fileList) {
    const candidates = Array.from(fileList);
    let rejected = 0;
    for (const file of candidates) {
      if (items.length >= maxFiles) {
        rejected++;
        continue;
      }
      if (file.size === 0 || file.size > maxFileBytes || !/\.(jpe?g|png|webp)$/i.test(file.name)) {
        rejected++;
        continue;
      }
      items.push({ file, url: URL.createObjectURL(file) });
    }
    renderSelection();
    showMessage(
      message,
      rejected ? `${rejected} file${rejected === 1 ? " was" : "s were"} skipped. Choose non-empty JPEG, PNG, or WebP images under 10 MB.` : "",
      rejected > 0,
    );
    fileInput.value = "";
  }

  function makeField(form, key, value) {
    if (value !== undefined && value !== null && value !== "") form.append(key, String(value));
  }

  function uploadOne(item, settings, onProgress) {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("files", item.file, item.file.name);
      form.append("session_id", sessionId);
      form.append("output_format", settings.output_format);
      form.append("quality", settings.quality);
      form.append("resize_mode", settings.resize_mode);
      makeField(form, "width", settings.width);
      makeField(form, "height", settings.height);
      form.append("allow_enlarge", String(settings.allow_enlarge));
      form.append("webp_lossless", String(settings.webp_lossless));

      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/compress");
      xhr.responseType = "json";
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total);
      };
      xhr.onerror = () => reject(new Error("Could not reach the local image processor."));
      xhr.onload = () => {
        const body = xhr.response || {};
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body.results?.[0] ?? { error: body.errors?.[0]?.message ?? "The image could not be processed." });
        } else {
          reject(new Error(body.detail || body.errors?.[0]?.message || "The image could not be processed."));
        }
      };
      xhr.send(form);
    });
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function renderResult(result, originalUrl) {
    const card = makeElement("article", "result-card");
    const top = makeElement("div", "result-top");
    const name = makeElement("div", "result-name", result.original_name);
    name.title = result.original_name;
    const actions = makeElement("div", "result-actions");
    const download = makeElement("a", "button button-secondary", "Download ↓");
    download.href = result.download_url;
    download.download = result.output_name;
    const remove = makeElement("button", "button button-quiet", "Remove");
    remove.type = "button";
    remove.addEventListener("click", () => deleteResult(result.id, card, originalUrl));
    actions.append(download, remove);
    top.append(name, actions);

    const comparison = makeElement("div", "comparison");
    const original = previewPanel("Original", originalUrl, formatBytes(result.original_size), `${result.original_width} × ${result.original_height}`);
    const optimized = previewPanel("Optimized", result.preview_url, formatBytes(result.output_size), `${result.output_width} × ${result.output_height}`);
    comparison.append(original, optimized);

    const stats = makeElement("div", "result-stats");
    const saved = result.saved_bytes >= 0
      ? `${formatBytes(result.saved_bytes)} saved (${result.saved_percentage.toFixed(1)}%)`
      : `${formatBytes(Math.abs(result.saved_bytes))} larger (${Math.abs(result.saved_percentage).toFixed(1)}%)`;
    const saving = makeElement("span", `saving${result.output_larger ? " negative" : ""}`, saved);
    stats.append(makeElement("span", "", `Original ${formatBytes(result.original_size)}`));
    stats.append(makeElement("span", "", `Optimized ${formatBytes(result.output_size)}`));
    stats.append(saving);
    card.append(top, comparison, stats);
    card.dataset.originalUrl = originalUrl;
    resultsList.prepend(card);
    resultsSection.hidden = false;
  }

  function previewPanel(label, src, size, dimensions) {
    const panel = makeElement("div", "preview-panel");
    const heading = makeElement("div", "preview-heading");
    heading.append(makeElement("span", "", label), makeElement("span", "", `${size} · ${dimensions}`));
    const frame = makeElement("div", "preview-frame");
    const image = document.createElement("img");
    image.src = src;
    image.alt = `${label} image preview`;
    frame.append(image);
    panel.append(heading, frame);
    return panel;
  }

  async function deleteResult(id, card, originalUrl) {
    try {
      const response = await fetch(`/api/results/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not remove this result.");
      const index = results.findIndex((entry) => entry.id === id);
      if (index >= 0) results.splice(index, 1);
      card.remove();
      URL.revokeObjectURL(originalUrl);
      if (!results.length) resultsSection.hidden = true;
      showMessage($("#results-message"), "");
    } catch (error) {
      showMessage($("#results-message"), error.message, true);
    }
  }

  async function compressSelected() {
    if (busy || !items.length) return;
    const selected = items.slice();
    const dimensions = resizeMode.value === "original" ? {} : {
      width: $("#resize-width").value ? Number($("#resize-width").value) : undefined,
      height: $("#resize-height").value ? Number($("#resize-height").value) : undefined,
    };
    if (resizeMode.value !== "original" && !dimensions.width && !dimensions.height) {
      showMessage(message, "Enter a width, a height, or both to resize.", true);
      return;
    }
    if ([dimensions.width, dimensions.height].some((value) => value !== undefined && (!Number.isInteger(value) || value < 1 || value > maxDimension))) {
      showMessage(message, `Resize dimensions must be whole numbers between 1 and ${maxDimension.toLocaleString()}.`, true);
      return;
    }
    const settings = {
      output_format: outputFormat.value,
      quality: quality.value,
      resize_mode: resizeMode.value,
      ...dimensions,
      webp_lossless: $("#webp-lossless").checked,
      allow_enlarge: $("#allow-enlarge").checked,
    };

    busy = true;
    renderSelection();
    progressArea.hidden = false;
    $("#progress-bar").value = 0;
    showMessage(message, "");
    showMessage($("#results-message"), "");
    const failures = [];
    for (let index = 0; index < selected.length; index++) {
      const item = selected[index];
      $("#progress-label").textContent = `Processing image ${index + 1} of ${selected.length}…`;
      try {
        const result = await uploadOne(item, settings, (fraction) => updateProgress(index, fraction, selected.length));
        if (result.error) {
          failures.push(`${item.file.name}: ${result.error}`);
        } else {
          results.push(result);
          renderResult(result, item.url);
          const currentIndex = items.indexOf(item);
          if (currentIndex >= 0) items.splice(currentIndex, 1);
          renderSelection();
        }
      } catch (error) {
        failures.push(`${item.file.name}: ${error.message}`);
      }
      updateProgress(index + 1, 0, selected.length);
    }
    busy = false;
    renderSelection();
    $("#progress-label").textContent = failures.length ? "Finished with some errors." : "Compression complete.";
    $("#progress-percent").textContent = "100%";
    $("#progress-bar").value = 100;
    showMessage(message, failures.join(" "));
    if (failures.length) showMessage(message, failures.join(" "), true);
  }

  function updateProgress(completed, fraction, total) {
    const percent = Math.round(((completed + fraction) / total) * 100);
    $("#progress-bar").value = percent;
    $("#progress-percent").textContent = `${percent}%`;
  }

  async function downloadAll() {
    if (!results.length) return;
    const button = $("#download-all");
    button.disabled = true;
    showMessage($("#results-message"), "Preparing your ZIP download…");
    try {
      const response = await fetch("/api/download-zip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, result_ids: results.map((item) => item.id) }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "Could not create the ZIP download.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "smart-image-compressor.zip";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showMessage($("#results-message"), "");
    } catch (error) {
      showMessage($("#results-message"), error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function clearResults() {
    try {
      const response = await fetch("/api/session", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!response.ok) throw new Error("Could not clear the current session.");
      resultsList.querySelectorAll(".result-card").forEach((card) => URL.revokeObjectURL(card.dataset.originalUrl));
      results.splice(0, results.length);
      resultsList.replaceChildren();
      resultsSection.hidden = true;
      showMessage($("#results-message"), "");
    } catch (error) {
      showMessage($("#results-message"), error.message, true);
    }
  }

  dropZone.addEventListener("click", (event) => {
    if (event.target !== fileInput) fileInput.click();
  });
  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => addFiles(fileInput.files));
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
    addFiles(event.dataTransfer.files);
  });
  $("#clear-selection").addEventListener("click", () => {
    items.forEach((item) => URL.revokeObjectURL(item.url));
    items.splice(0, items.length);
    renderSelection();
    showMessage(message, "");
  });
  $("#compress-button").addEventListener("click", compressSelected);
  $("#download-all").addEventListener("click", downloadAll);
  $("#clear-results").addEventListener("click", clearResults);
  quality.addEventListener("input", () => { $("#quality-value").value = quality.value; });
  resizeMode.addEventListener("change", () => { dimensionFields.hidden = resizeMode.value === "original"; });
  outputFormat.addEventListener("change", () => {
    const format = outputFormat.value;
    $("#lossless-control").hidden = format !== "webp";
    $("#format-note").textContent = format === "png"
      ? "PNG uses lossless optimization and preserves transparency. The quality setting does not affect PNG output."
      : format === "jpeg"
        ? "JPEG uses the selected quality and cannot preserve transparency; transparent areas are composited onto white."
        : "WebP uses lossy compression at the selected quality. Transparency is preserved.";
  });

  fetch("/api/config")
    .then((response) => {
      if (!response.ok) throw new Error("Could not load upload limits.");
      return response.json();
    })
    .then((config) => {
      maxFiles = config.max_batch_files;
      maxFileBytes = config.max_upload_bytes;
      maxDimension = config.max_image_dimension;
      $("#upload-guidance").textContent =
        `JPEG, PNG, or WebP · Up to ${config.max_upload_mb} MB each · ${maxFiles} images at a time`;
      $("#resize-width").max = String(maxDimension);
      $("#resize-height").max = String(maxDimension);
    })
    .catch((error) => showMessage(message, error.message, true));
})();
