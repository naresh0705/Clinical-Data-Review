let allFlags = [];
let sortCol = null;
let sortAsc = true;
let pollTimer = null;
let uploadedFiles = {};

const EXPECTED_FILES = [
    "Demographics.csv", "Medical_History.csv", "Concomitant_Meds.csv",
    "Adverse_Events.csv", "Lab_Data.csv", "Vital_Signs.csv", "Disposition.csv"
];

document.addEventListener("DOMContentLoaded", function () {
    const dropZone = document.getElementById("file-drop");
    if (dropZone) {
        dropZone.addEventListener("dragover", function (e) {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        dropZone.addEventListener("dragleave", function () {
            dropZone.classList.remove("dragover");
        });
        dropZone.addEventListener("drop", function (e) {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            handleFiles(e.dataTransfer.files);
        });
    }
});

// ── Navigation ──────────────────────────────────────────────────────────────

function showPage(pageId) {
    document.querySelectorAll(".page").forEach(function (p) { p.classList.remove("active"); });
    var el = document.getElementById("page-" + pageId);
    if (el) el.classList.add("active");
    document.querySelectorAll("nav button").forEach(function (b) {
        b.classList.toggle("active", b.dataset.page === pageId);
    });
}

// ── File Upload ─────────────────────────────────────────────────────────────

function handleFiles(fileList) {
    for (var i = 0; i < fileList.length; i++) {
        var f = fileList[i];
        if (!f.name.toLowerCase().endsWith(".csv")) continue;
        var match = null;
        for (var j = 0; j < EXPECTED_FILES.length; j++) {
            if (EXPECTED_FILES[j].toLowerCase() === f.name.toLowerCase()) {
                match = EXPECTED_FILES[j];
                break;
            }
        }
        if (match) {
            uploadedFiles[match] = f;
        } else {
            uploadedFiles[f.name] = f;
        }
    }
    renderFileList();
}

function renderFileList() {
    var el = document.getElementById("file-list");
    if (!el) return;
    var html = "";
    var allPresent = true;
    var missing = [];
    for (var i = 0; i < EXPECTED_FILES.length; i++) {
        var name = EXPECTED_FILES[i];
        var ok = uploadedFiles[name] ? true : false;
        if (!ok) {
            allPresent = false;
            missing.push(name);
        }
        html += '<div class="file-item ' + (ok ? 'ok' : 'missing') + '">' +
                (ok ? '&#10003; ' : '&#10007; ') + name + '</div>';
    }
    if (Object.keys(uploadedFiles).length > 0 && !allPresent) {
        html += '<div class="file-item missing" style="margin-top:0.5rem;font-weight:600">Missing: ' + missing.join(", ") + '</div>';
    }
    el.innerHTML = html;
    var btn = document.getElementById("btn-analyze");
    if (btn) {
        btn.disabled = !allPresent;
        btn.style.opacity = allPresent ? "1" : "0.5";
    }
}

// ── Analysis ────────────────────────────────────────────────────────────────

function runAnalysis() {
    var btn = document.getElementById("btn-analyze");
    btn.disabled = true;
    btn.textContent = "Running...";

    var progressEl = document.getElementById("progress-bar");
    progressEl.classList.remove("hidden");
    document.getElementById("progress-fill").style.width = "30%";
    document.getElementById("progress-text").textContent = "Uploading files...";

    var formData = new FormData();
    for (var i = 0; i < EXPECTED_FILES.length; i++) {
        var name = EXPECTED_FILES[i];
        if (!uploadedFiles[name]) {
            alert("Missing file: " + name);
            btn.disabled = false;
            btn.textContent = "Run Analysis";
            return;
        }
        formData.append("files", uploadedFiles[name]);
    }

    fetch("/api/upload", { method: "POST", body: formData })
        .then(function (uploadRes) {
            if (!uploadRes.ok) {
                return uploadRes.json().then(function (err) {
                    throw new Error(err.detail || "Upload failed: HTTP " + uploadRes.status);
                });
            }
            return uploadRes.json();
        })
        .then(function (uploadData) {
            document.getElementById("progress-fill").style.width = "50%";
            document.getElementById("progress-text").textContent = "Uploaded " + uploadData.subjects + " subjects. Starting analysis...";

            var provider = document.getElementById("llm-provider").value;
            var reqBody = provider === "skip"
                ? { skip_llm: true }
                : { skip_llm: false, llm_provider: provider };

            return fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(reqBody),
            });
        })
        .then(function (analyzeRes) {
            if (!analyzeRes.ok) {
                return analyzeRes.json().then(function (err) {
                    throw new Error(err.detail || "Analysis failed: HTTP " + analyzeRes.status);
                });
            }
            return analyzeRes.json();
        })
        .then(function (data) {
            if (data.status === "complete" && data.results) {
                document.getElementById("progress-fill").style.width = "100%";
                document.getElementById("progress-text").textContent = "Complete!";
                btn.textContent = "Run Analysis";
                allFlags = data.results.flags;
                renderSummary(data.results);
                renderFlagsTable(allFlags);
                document.getElementById("nav").classList.remove("hidden");
                showPage("summary");
            } else if (data.status === "error") {
                throw new Error(data.error || "Analysis failed");
            } else {
                pollStatus();
            }
        })
        .catch(function (e) {
            alert("Error: " + e.message);
            btn.disabled = false;
            btn.textContent = "Run Analysis";
            progressEl.classList.add("hidden");
        });
}

function pollStatus() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
        fetch("/api/status")
            .then(function (res) { return res.json(); })
            .then(function (data) {
                document.getElementById("progress-text").textContent = data.progress || data.status;
                if (data.status === "running") {
                    document.getElementById("progress-fill").style.width = "70%";
                } else if (data.status === "complete") {
                    clearInterval(pollTimer);
                    document.getElementById("progress-fill").style.width = "100%";
                    document.getElementById("progress-text").textContent = "Complete! Loading results...";
                    document.getElementById("btn-analyze").textContent = "Run Analysis";
                    loadResults();
                } else if (data.status === "error") {
                    clearInterval(pollTimer);
                    document.getElementById("progress-text").textContent = "Error: " + data.progress;
                    document.getElementById("btn-analyze").disabled = false;
                    document.getElementById("btn-analyze").textContent = "Run Analysis";
                }
            })
            .catch(function () {});
    }, 1500);
}

function loadResults() {
    fetch("/api/results")
        .then(function (res) { return res.json(); })
        .then(function (data) {
            allFlags = data.flags;
            renderSummary(data);
            renderFlagsTable(allFlags);
            document.getElementById("nav").classList.remove("hidden");
            showPage("summary");
        })
        .catch(function (e) {
            alert("Failed to load results: " + e.message);
        });
}

// ── Summary ─────────────────────────────────────────────────────────────────

function renderSummary(data) {
    document.getElementById("stat-subjects").textContent = data.total_subjects;
    document.getElementById("stat-flags").textContent = data.total_flags;
    document.getElementById("stat-critical").textContent = data.critical_count;
    document.getElementById("stat-major").textContent = data.major_count;
    document.getElementById("stat-minor").textContent = data.minor_count;
    document.getElementById("stat-time-saved").textContent = data.estimated_hours_saved;
    document.getElementById("stat-rule-flags").textContent = data.rule_flags;
    document.getElementById("stat-ai-flags").textContent = data.ai_flags;
    document.getElementById("stat-processing-time").textContent = data.processing_time_seconds;
    if (data.llm_provider) {
        document.getElementById("llm-info-row").style.display = "flex";
        document.getElementById("stat-llm-info").textContent = data.llm_provider + " (" + data.llm_model + ")";
    }
}

// ── Flags Table ─────────────────────────────────────────────────────────────

function renderFlagsTable(flags) {
    var tbody = document.getElementById("flags-tbody");
    tbody.innerHTML = "";
    for (var i = 0; i < flags.length; i++) {
        var f = flags[i];
        var tr = document.createElement("tr");
        tr.className = "flag-row";
        tr.setAttribute("data-index", i);
        (function (idx) {
            tr.onclick = function () { toggleExpand(idx); };
        })(i);
        tr.innerHTML =
            '<td><span class="subject-link" onclick="event.stopPropagation(); showSubject(\'' + f.subject_id + '\')">' + f.subject_id + '</span></td>' +
            '<td>' + f.forms_involved.join(" + ") + '</td>' +
            '<td>' + truncate(f.description, 120) + '</td>' +
            '<td><span class="badge severity-' + f.severity.toLowerCase() + '">' + f.severity + '</span></td>' +
            '<td><span class="badge ' + (f.source === 'Rule' ? 'rule' : 'ai') + '">' + f.source + '</span></td>' +
            '<td>' + f.rule_id + '</td>';
        tbody.appendChild(tr);
    }
    document.getElementById("flags-count").textContent = flags.length + " flags";
}

function truncate(s, n) {
    return s.length > n ? s.substring(0, n) + "..." : s;
}

function toggleExpand(index) {
    var tbody = document.getElementById("flags-tbody");
    var row = tbody.querySelector('tr[data-index="' + index + '"]');
    var existing = tbody.querySelector('tr.expanded-row[data-expand="' + index + '"]');
    if (existing) {
        existing.remove();
        if (row) row.classList.remove("expanded");
        return;
    }
    var allExp = tbody.querySelectorAll("tr.expanded-row");
    for (var i = 0; i < allExp.length; i++) allExp[i].remove();
    var allExpanded = tbody.querySelectorAll("tr.expanded");
    for (var i = 0; i < allExpanded.length; i++) allExpanded[i].classList.remove("expanded");

    if (row) row.classList.add("expanded");
    var f = getFilteredFlags()[index];
    var expTr = document.createElement("tr");
    expTr.className = "expanded-row";
    expTr.setAttribute("data-expand", index);
    var html = '<td colspan="6"><div class="expanded-content">' +
        '<h4>' + f.rule_id + ': ' + f.subject_id + '</h4>' +
        '<p><strong>Forms:</strong> ' + f.forms_involved.join(", ") + '</p>' +
        '<p><strong>Description:</strong> ' + f.description + '</p>' +
        '<p><strong>Confidence:</strong> ' + f.confidence + '</p>';
    if (f.suggested_query) {
        html += '<div><strong>Suggested Query:</strong><div class="query-box">' + f.suggested_query + '</div></div>';
    }
    html += '</div></td>';
    expTr.innerHTML = html;
    if (row) row.after(expTr);
}

function sortTable(col) {
    if (sortCol === col) {
        sortAsc = !sortAsc;
    } else {
        sortCol = col;
        sortAsc = true;
    }
    var flags = getFilteredFlags();
    flags.sort(function (a, b) {
        var va = col === "forms_involved" ? a[col].join(", ") : (a[col] || "");
        var vb = col === "forms_involved" ? b[col].join(", ") : (b[col] || "");
        if (col === "severity") {
            var order = { Critical: 0, Major: 1, Minor: 2 };
            va = order[va] !== undefined ? order[va] : 3;
            vb = order[vb] !== undefined ? order[vb] : 3;
        }
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    });
    renderFlagsTable(flags);
}

function getFilteredFlags() {
    var sev = document.getElementById("filter-severity").value;
    var src = document.getElementById("filter-source").value;
    var search = document.getElementById("filter-search").value.toLowerCase();
    return allFlags.filter(function (f) {
        if (sev && f.severity !== sev) return false;
        if (src && f.source !== src) return false;
        if (search && f.subject_id.toLowerCase().indexOf(search) === -1 &&
            f.description.toLowerCase().indexOf(search) === -1 &&
            f.rule_id.toLowerCase().indexOf(search) === -1) return false;
        return true;
    });
}

function applyFilters() {
    renderFlagsTable(getFilteredFlags());
}

function exportCSV() {
    window.location.href = "/api/results/export";
}

// ── Subject Detail ──────────────────────────────────────────────────────────

function showSubject(subjectId) {
    fetch("/api/results/subject/" + subjectId)
        .then(function (res) {
            if (!res.ok) throw new Error("Subject not found");
            return res.json();
        })
        .then(function (data) {
            renderSubjectDetail(data.profile, data.flags);
            showPage("subject");
        })
        .catch(function (e) { alert(e.message); });
}

function renderSubjectDetail(profile, flags) {
    var dem = profile.demographics;
    document.getElementById("subject-header").innerHTML =
        '<h2>Subject: ' + profile.subject_id + '</h2>' +
        '<div class="dem-grid">' +
        '<div class="dem-item"><span>Site:</span> <strong>' + (dem.Site_ID || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>DOB:</span> <strong>' + (dem.DOB || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>Sex:</span> <strong>' + (dem.Sex || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>Race:</span> <strong>' + (dem.Race || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>Screening:</span> <strong>' + (dem.Screening_Date || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>Consent:</span> <strong>' + (dem.Informed_Consent_Date || "N/A") + '</strong></div>' +
        '<div class="dem-item"><span>Status:</span> <strong>' + (profile.disposition.Status || "N/A") + '</strong></div>' +
        '</div>';

    var flagsHtml = '<h3>Flags (' + flags.length + ')</h3>';
    if (flags.length === 0) {
        flagsHtml += '<p style="color:var(--text-muted)">No issues found for this subject.</p>';
    } else {
        for (var i = 0; i < flags.length; i++) {
            var f = flags[i];
            flagsHtml += '<div class="subject-flag-item sev-' + f.severity + '">' +
                '<span class="badge severity-' + f.severity.toLowerCase() + '">' + f.severity + '</span> ' +
                '<span class="badge ' + (f.source === 'Rule' ? 'rule' : 'ai') + '">' + f.source + '</span> ' +
                '<strong>' + f.rule_id + '</strong>: ' + f.description;
            if (f.suggested_query) {
                flagsHtml += '<div class="query-box" style="margin-top:0.5rem">' + f.suggested_query + '</div>';
            }
            flagsHtml += '</div>';
        }
    }
    document.getElementById("subject-flags").innerHTML = flagsHtml;

    var sections = [
        { title: "Medical History", data: profile.medical_history, cols: ["MH_Term", "MH_Start_Date", "MH_End_Date", "Ongoing_YN"] },
        { title: "Concomitant Medications", data: profile.concomitant_meds, cols: ["Med_Name", "Indication", "Start_Date", "End_Date", "Ongoing_YN"] },
        { title: "Adverse Events", data: profile.adverse_events, cols: ["AE_Term", "AE_Verbatim", "Severity", "Seriousness", "Causality", "Start_Date", "Outcome", "Action_Taken"] },
        { title: "Lab Data", data: profile.lab_data, cols: ["Visit_Name", "Lab_Test", "Result", "Unit", "Normal_Range_Low", "Normal_Range_High"] },
        { title: "Vital Signs", data: profile.vital_signs, cols: ["Visit_Name", "BP_Systolic", "BP_Diastolic", "Weight_kg", "Heart_Rate"] },
    ];

    var detailsHtml = "";
    for (var s = 0; s < sections.length; s++) {
        var sec = sections[s];
        if (!sec.data || sec.data.length === 0) continue;
        detailsHtml += '<div class="detail-section"><h3>' + sec.title + ' (' + sec.data.length + ')</h3>' +
            '<table class="detail-table"><thead><tr>';
        for (var c = 0; c < sec.cols.length; c++) {
            detailsHtml += '<th>' + sec.cols[c].replace(/_/g, " ") + '</th>';
        }
        detailsHtml += '</tr></thead><tbody>';
        for (var r = 0; r < sec.data.length; r++) {
            detailsHtml += '<tr>';
            for (var c = 0; c < sec.cols.length; c++) {
                var val = sec.data[r][sec.cols[c]];
                detailsHtml += '<td>' + (val != null ? val : '') + '</td>';
            }
            detailsHtml += '</tr>';
        }
        detailsHtml += '</tbody></table></div>';
    }
    document.getElementById("subject-details").innerHTML = detailsHtml;
}
