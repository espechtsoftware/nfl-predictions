(() => {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const views = {
    presets: "preset-registry",
    lineage: "strategy-lineage",
    metrics: "paired-heldout-fill-retrieval-comparison",
    promotions: "active-pointer-promotion-traversal",
    structure: "lineup-player-team-game-traversal",
    census: "registry-firewall-census",
  };
  const state = { projection: null, rows: {}, selectedLineup: "" };

  const $ = (id) => document.getElementById(id);
  const finite = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const uniq = (values) => [...new Set(values.filter((value) => value !== ""))];
  const mean = (values) => {
    const clean = values.map(finite).filter((value) => value !== null);
    return clean.length ? clean.reduce((sum, value) => sum + value, 0) / clean.length : null;
  };
  const short = (value, length = 24) => {
    const text = String(value ?? "—")
      .replace(/^fillpreset:/i, "")
      .replace(/^retrievalpreset:/i, "")
      .replace(/^experiment:/i, "")
      .replace(/^snapshot:/i, "")
      .replace(/^winner:/i, "");
    return text.length > length ? `${text.slice(0, length - 1)}…` : text;
  };
  const format = (value) => {
    const number = finite(value);
    if (number === null) return "—";
    const magnitude = Math.abs(number);
    if (magnitude >= 1000) return number.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (magnitude >= 100) return number.toFixed(1);
    if (magnitude >= 10) return number.toFixed(2);
    return number.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  };
  const parseRecord = (value) => {
    if (value && typeof value === "object" && !Array.isArray(value)) return value;
    if (typeof value !== "string" || !value) return {};
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
      return {};
    }
  };
  const splitName = (value) => String(value ?? "unspecified").toLowerCase();
  const strategyLabel = (row) => `${short(row.fill_preset, 16)} · ${short(row.retrieval_preset, 16)}`;

  function svgNode(tag, attributes = {}, text = null) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== null) node.textContent = String(text);
    return node;
  }

  function titleFor(node, text) {
    node.appendChild(svgNode("title", {}, text));
    return node;
  }

  function clearSvg(svg) {
    svg.replaceChildren();
  }

  function emptyChart(svg, title, copy) {
    clearSvg(svg);
    svg.appendChild(svgNode("text", { x: "50%", y: "47%", "text-anchor": "middle", class: "empty-title" }, title));
    svg.appendChild(svgNode("text", { x: "50%", y: "54%", "text-anchor": "middle", class: "empty-copy" }, copy));
  }

  function setOptions(select, options, preferred = null) {
    const retained = preferred ?? select.value;
    select.replaceChildren();
    options.forEach(({ value, label }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    if (options.some((option) => option.value === retained)) select.value = retained;
  }

  function metricNames() {
    return uniq((state.rows[views.metrics] || []).map((row) => String(row.metric_name ?? ""))).sort();
  }

  function preferredMetric(names, patterns, fallback = 0) {
    for (const pattern of patterns) {
      const match = names.find((name) => pattern.test(name));
      if (match) return match;
    }
    return names[fallback] || "";
  }

  function colorRamp(value, minimum, maximum) {
    const start = [255, 128, 110];
    const end = [103, 224, 193];
    const ratio = maximum === minimum ? .55 : Math.max(0, Math.min(1, (value - minimum) / (maximum - minimum)));
    const rgb = start.map((channel, index) => Math.round(channel + (end[index] - channel) * ratio));
    return `rgb(${rgb.join(",")})`;
  }

  function populateControls() {
    const lineageRows = state.rows[views.lineage] || [];
    const structureRows = state.rows[views.structure] || [];
    const slates = uniq(lineageRows.map((row) => String(row.slate_id ?? ""))).sort();
    setOptions($("lineage-slate"), [
      { value: "__all__", label: "All slates" },
      ...slates.map((slate) => ({ value: slate, label: short(slate, 32) })),
    ]);

    const metrics = metricNames();
    const metricOptions = metrics.map((metric) => ({ value: metric, label: short(metric, 38) }));
    const coverage = preferredMetric(metrics, [/200/, /coverage/i, /tail/i]);
    const diversity = preferredMetric(metrics, [/divers/i, /entropy/i, /unique/i, /overlap/i], Math.min(1, metrics.length - 1));
    setOptions($("heat-metric"), metricOptions, coverage);
    setOptions($("paired-metric"), metricOptions, coverage);
    setOptions($("scatter-x"), metricOptions, coverage);
    setOptions($("scatter-y"), metricOptions, diversity);

    const splits = uniq((state.rows[views.metrics] || []).map((row) => splitName(row.split))).sort();
    const preferredSplit = splits.includes("heldout") ? "heldout" : splits[0];
    setOptions($("heat-split"), splits.map((split) => ({ value: split, label: split })), preferredSplit);

    const networkSlates = uniq(structureRows.map((row) => String(row.slate_id ?? ""))).sort();
    setOptions($("network-slate"), [
      { value: "__all__", label: "All slates" },
      ...networkSlates.map((slate) => ({ value: slate, label: short(slate, 32) })),
    ]);
    refreshNetworkLineups();
  }

  function drawPresetCatalog() {
    const catalog = $("preset-catalog");
    catalog.replaceChildren();
    const rows = (state.rows[views.presets] || []).slice().sort((left, right) =>
      String(left.preset_kind).localeCompare(String(right.preset_kind)) ||
      String(left.preset_id).localeCompare(String(right.preset_id)) ||
      Number(left.preset_version || 0) - Number(right.preset_version || 0));
    if (!rows.length) {
      const card = document.createElement("div");
      card.className = "preset-card";
      const copy = document.createElement("p");
      copy.textContent = "No versioned presets are present in this projection.";
      card.appendChild(copy);
      catalog.appendChild(card);
      return;
    }
    rows.forEach((row) => {
      const record = parseRecord(row.preset_record);
      const kind = String(row.preset_kind || "Preset");
      const card = document.createElement("article");
      card.className = `preset-card ${kind.toLowerCase().includes("retrieval") ? "retrieval" : "fill"}`;
      const type = document.createElement("div");
      type.className = "type";
      type.textContent = `${kind.replace("Preset", " preset")} · v${record.version ?? row.preset_version ?? "—"}`;
      const heading = document.createElement("h3");
      heading.textContent = short(row.preset_id, 34);
      const description = document.createElement("p");
      description.textContent = String(record.description ?? (record.deprecated === true ? "Deprecated preset" : "Versioned research preset"));
      const parameters = document.createElement("div");
      parameters.className = "parameter-list";
      const values = Array.isArray(record.parameters) ? record.parameters : [];
      values.slice(0, 6).forEach((parameter) => {
        const chip = document.createElement("span");
        chip.textContent = `${parameter.name}=${String(parameter.value)}`;
        parameters.appendChild(chip);
      });
      card.append(type, heading, description, parameters);
      catalog.appendChild(card);
    });
  }

  function drawLineage() {
    const svg = $("lineage-chart");
    const selectedSlate = $("lineage-slate").value;
    const rows = (state.rows[views.lineage] || []).filter(
      (row) => selectedSlate === "__all__" || String(row.slate_id) === selectedSlate,
    );
    if (!rows.length) {
      emptyChart(svg, "No lineage rows", "This slate has not been projected into the research graph.");
      return;
    }
    clearSvg(svg);
    const columns = [
      { key: "fill_preset", record: "fill_preset_record", title: "FILL PRESET", x: 44, color: "#67e0c1" },
      { key: "snapshot_id", record: "snapshot_record", title: "CORPUS SNAPSHOT", x: 306, color: "#a7ed68" },
      { key: "retrieval_preset", record: "retrieval_preset_record", title: "RETRIEVAL PRESET", x: 568, color: "#6ea8ff" },
      { key: "experiment_id", record: "experiment_record", title: "EXPERIMENT", x: 830, color: "#ffca72" },
    ];
    const width = 205;
    const nodeMaps = new Map();
    columns.forEach((column) => {
      const records = new Map();
      rows.forEach((row) => {
        const id = String(row[column.key] ?? "");
        if (id && !records.has(id)) records.set(id, parseRecord(row[column.record]));
      });
      const all = [...records.entries()];
      const visible = all.slice(0, 9);
      const gap = Math.min(57, 320 / Math.max(1, visible.length - 1));
      const top = visible.length === 1 ? 205 : 78;
      const locations = new Map();
      visible.forEach(([id, record], index) => {
        locations.set(id, { x: column.x, y: top + index * gap, record });
      });
      nodeMaps.set(column.key, locations);
      svg.appendChild(svgNode("text", { x: column.x, y: 34, class: "axis-label", "font-weight": 800 }, column.title));
      if (all.length > visible.length) {
        svg.appendChild(svgNode("text", { x: column.x, y: 410, class: "axis-label" }, `+ ${all.length - visible.length} more`));
      }
    });

    const edges = new Set();
    rows.forEach((row) => {
      for (let index = 0; index < columns.length - 1; index += 1) {
        const left = columns[index];
        const right = columns[index + 1];
        const leftId = String(row[left.key] ?? "");
        const rightId = String(row[right.key] ?? "");
        const from = nodeMaps.get(left.key).get(leftId);
        const to = nodeMaps.get(right.key).get(rightId);
        const edgeId = `${index}|${leftId}|${rightId}`;
        if (!from || !to || edges.has(edgeId)) continue;
        edges.add(edgeId);
        const startX = from.x + width;
        const endX = to.x;
        const bend = (endX - startX) * .52;
        svg.appendChild(svgNode("path", {
          d: `M ${startX} ${from.y} C ${startX + bend} ${from.y}, ${endX - bend} ${to.y}, ${endX} ${to.y}`,
          fill: "none", stroke: "rgba(145,196,194,.22)", "stroke-width": 1.35,
        }));
      }
    });

    columns.forEach((column) => {
      nodeMaps.get(column.key).forEach(({ x, y, record }, id) => {
        const group = svgNode("g", { class: "tooltip-target" });
        group.appendChild(svgNode("rect", {
          x, y: y - 20, width, height: 40, rx: 8,
          fill: "rgba(7,20,23,.95)", stroke: column.color, "stroke-opacity": .54,
        }));
        group.appendChild(svgNode("circle", { cx: x + 13, cy: y, r: 4, fill: column.color }));
        group.appendChild(svgNode("text", { x: x + 25, y: y - 2, "font-size": 10.5, "font-weight": 720 }, short(id, 29)));
        const version = record.version ?? record.preset_version ?? record.task_index ?? "";
        group.appendChild(svgNode("text", { x: x + 25, y: y + 11, "font-size": 8.5, fill: "#829a9e" }, version === "" ? short(record.description ?? "registered", 34) : `version ${version}`));
        titleFor(group, `${id}\n${record.description ?? record.created_at_utc ?? "Receipt-bound graph entity"}`);
        svg.appendChild(group);
      });
    });
  }

  function drawHeatmap() {
    const svg = $("heatmap-chart");
    const metric = $("heat-metric").value;
    const split = $("heat-split").value;
    const rows = (state.rows[views.metrics] || []).filter(
      (row) => String(row.metric_name) === metric && splitName(row.split) === split && finite(row.value) !== null,
    );
    if (!rows.length) {
      emptyChart(svg, "No metric surface", "Select a metric and split with completed experiments.");
      return;
    }
    const fills = uniq(rows.map((row) => String(row.fill_preset))).sort();
    const retrievals = uniq(rows.map((row) => String(row.retrieval_preset))).sort();
    const cells = new Map();
    rows.forEach((row) => {
      const key = `${row.fill_preset}\u0000${row.retrieval_preset}`;
      if (!cells.has(key)) cells.set(key, []);
      cells.get(key).push(Number(row.value));
    });
    const values = [...cells.values()].map(mean).filter((value) => value !== null);
    if (!values.length) {
      emptyChart(svg, "No numeric values", "The selected metric has no finite observations.");
      return;
    }
    clearSvg(svg);
    const left = 155;
    const top = 54;
    const right = 24;
    const bottom = 110;
    const cellW = (720 - left - right) / Math.max(1, retrievals.length);
    const cellH = (430 - top - bottom) / Math.max(1, fills.length);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    fills.forEach((fill, rowIndex) => {
      svg.appendChild(svgNode("text", {
        x: left - 10, y: top + rowIndex * cellH + cellH / 2 + 4,
        "text-anchor": "end", "font-size": 9.5,
      }, short(fill, 22)));
      retrievals.forEach((retrieval, columnIndex) => {
        const value = mean(cells.get(`${fill}\u0000${retrieval}`) || []);
        const x = left + columnIndex * cellW;
        const y = top + rowIndex * cellH;
        const rect = svgNode("rect", {
          x: x + 1.5, y: y + 1.5, width: Math.max(1, cellW - 3), height: Math.max(1, cellH - 3), rx: 5,
          fill: value === null ? "rgba(130,150,154,.08)" : colorRamp(value, minimum, maximum),
          "fill-opacity": value === null ? .4 : .83,
        });
        titleFor(rect, `${fill}\n${retrieval}\n${metric} (${split}): ${format(value)}`);
        svg.appendChild(rect);
        if (value !== null && cellW > 43 && cellH > 24) {
          svg.appendChild(svgNode("text", {
            x: x + cellW / 2, y: y + cellH / 2 + 3,
            "text-anchor": "middle", "font-size": 8.5, fill: "#071316", "font-weight": 800,
          }, format(value)));
        }
      });
    });
    retrievals.forEach((retrieval, index) => {
      svg.appendChild(svgNode("text", {
        x: left + index * cellW + cellW / 2, y: top + fills.length * cellH + 13,
        transform: `rotate(48 ${left + index * cellW + cellW / 2} ${top + fills.length * cellH + 13})`,
        "text-anchor": "start", "font-size": 9,
      }, short(retrieval, 22)));
    });
    svg.appendChild(svgNode("text", { x: left, y: 20, class: "axis-label" }, `${short(metric, 56)} · ${split} · slate mean`));
    const legendX = 520;
    for (let index = 0; index < 70; index += 1) {
      const value = minimum + (maximum - minimum) * index / 69;
      svg.appendChild(svgNode("rect", { x: legendX + index * 2, y: 17, width: 2.2, height: 8, fill: colorRamp(value, minimum, maximum) }));
    }
    svg.appendChild(svgNode("text", { x: legendX, y: 38, class: "axis-label" }, format(minimum)));
    svg.appendChild(svgNode("text", { x: legendX + 140, y: 38, class: "axis-label", "text-anchor": "end" }, format(maximum)));
  }

  function pairedRows(metric) {
    const all = (state.rows[views.metrics] || []).filter((row) => String(row.metric_name) === metric && finite(row.value) !== null);
    const lookup = new Map();
    all.forEach((row) => lookup.set(`${row.experiment_id}\u0000${splitName(row.split)}`, Number(row.value)));
    const grouped = new Map();
    all.forEach((row) => {
      if (!row.paired_baseline) return;
      const baseline = lookup.get(`${row.paired_baseline}\u0000${splitName(row.split)}`);
      if (!Number.isFinite(baseline)) return;
      const label = strategyLabel(row);
      if (!grouped.has(label)) grouped.set(label, { label, discovery: [], heldout: [], other: [] });
      const bucket = splitName(row.split).includes("held") ? "heldout" : splitName(row.split).includes("discover") ? "discovery" : "other";
      grouped.get(label)[bucket].push(Number(row.value) - baseline);
    });
    return [...grouped.values()].map((row) => ({
      label: row.label,
      discovery: mean(row.discovery.length ? row.discovery : row.other),
      heldout: mean(row.heldout),
      primaryLabel: row.discovery.length ? "Discovery" : "All-worlds descriptive",
    })).filter((row) => row.discovery !== null || row.heldout !== null);
  }

  function drawPaired() {
    const svg = $("paired-chart");
    const metric = $("paired-metric").value;
    const rows = pairedRows(metric)
      .sort((left, right) => Math.abs(right.heldout ?? right.discovery ?? 0) - Math.abs(left.heldout ?? left.discovery ?? 0))
      .slice(0, 10);
    if (!rows.length) {
      emptyChart(svg, "No paired deltas", "Paired baseline rows will appear after matched experiments complete.");
      return;
    }
    clearSvg(svg);
    const values = rows.flatMap((row) => [row.discovery, row.heldout]).filter((value) => value !== null);
    const extent = Math.max(.001, ...values.map((value) => Math.abs(value))) * 1.16;
    const left = 58;
    const right = 24;
    const top = 34;
    const bottom = 108;
    const y = (value) => top + (extent - value) / (extent * 2) * (430 - top - bottom);
    const zeroY = y(0);
    [-1, -.5, 0, .5, 1].forEach((fraction) => {
      const value = extent * fraction;
      const py = y(value);
      svg.appendChild(svgNode("line", { x1: left, x2: 720 - right, y1: py, y2: py, class: fraction === 0 ? "axis" : "gridline" }));
      svg.appendChild(svgNode("text", { x: left - 8, y: py + 3, "text-anchor": "end", class: "axis-label" }, format(value)));
    });
    const step = (720 - left - right) / Math.max(1, rows.length);
    rows.forEach((row, index) => {
      const x = left + step * index + step / 2;
      if (row.discovery !== null && row.heldout !== null) {
        svg.appendChild(svgNode("line", { x1: x, x2: x, y1: y(row.discovery), y2: y(row.heldout), stroke: "rgba(197,217,219,.38)", "stroke-width": 2 }));
      }
      const stable = row.discovery !== null && row.heldout !== null && Math.sign(row.discovery) === Math.sign(row.heldout);
      [[row.discovery, "#ffca72", -4, row.primaryLabel], [row.heldout, "#6ea8ff", 4, "Held-out"]].forEach(([value, color, offset, label]) => {
        if (value === null) return;
        const circle = svgNode("circle", { cx: x + offset, cy: y(value), r: 5.3, fill: color, stroke: stable ? "#a7ed68" : "rgba(255,255,255,.22)", "stroke-width": stable ? 2 : 1 });
        titleFor(circle, `${row.label}\n${label} delta: ${format(value)}`);
        svg.appendChild(circle);
      });
      svg.appendChild(svgNode("text", {
        x, y: 430 - bottom + 17,
        transform: `rotate(43 ${x} ${430 - bottom + 17})`,
        "text-anchor": "start", "font-size": 8.5,
      }, short(row.label, 25)));
    });
    svg.appendChild(svgNode("text", { x: left, y: 18, class: "axis-label" }, `Challenger minus paired baseline · ${short(metric, 55)}`));
    svg.appendChild(svgNode("text", { x: 720 - right, y: zeroY - 6, "text-anchor": "end", class: "axis-label" }, "baseline"));
  }

  function experimentMetric(metric) {
    const rows = (state.rows[views.metrics] || []).filter((row) => String(row.metric_name) === metric && finite(row.value) !== null);
    const grouped = new Map();
    rows.forEach((row) => {
      const key = String(row.experiment_id);
      if (!grouped.has(key)) grouped.set(key, { heldout: [], discovery: [], other: [], row });
      const split = splitName(row.split);
      const bucket = split.includes("held") ? "heldout" : split.includes("discover") ? "discovery" : "other";
      grouped.get(key)[bucket].push(Number(row.value));
    });
    const values = new Map();
    grouped.forEach((group, key) => {
      const bucket = group.heldout.length ? group.heldout : group.discovery.length ? group.discovery : group.other;
      values.set(key, { value: mean(bucket), row: group.row, split: group.heldout.length ? "heldout" : group.discovery.length ? "discovery" : "other" });
    });
    return values;
  }

  function drawScatter() {
    const svg = $("scatter-chart");
    const xMetric = $("scatter-x").value;
    const yMetric = $("scatter-y").value;
    const xs = experimentMetric(xMetric);
    const ys = experimentMetric(yMetric);
    const points = [...xs.entries()].filter(([id, item]) => ys.has(id) && item.value !== null && ys.get(id).value !== null).map(([id, item]) => ({
      id, x: item.value, y: ys.get(id).value, row: item.row,
      split: item.split === "heldout" && ys.get(id).split === "heldout" ? "heldout" : "mixed",
    }));
    if (!points.length) {
      emptyChart(svg, "No joint metric rows", "Coverage and diversity must be recorded for the same experiments.");
      return;
    }
    clearSvg(svg);
    const left = 68;
    const right = 25;
    const top = 32;
    const bottom = 72;
    const xValues = points.map((point) => point.x);
    const yValues = points.map((point) => point.y);
    const xMinRaw = Math.min(...xValues);
    const xMaxRaw = Math.max(...xValues);
    const yMinRaw = Math.min(...yValues);
    const yMaxRaw = Math.max(...yValues);
    const xPad = Math.max((xMaxRaw - xMinRaw) * .12, Math.abs(xMaxRaw || 1) * .02, .001);
    const yPad = Math.max((yMaxRaw - yMinRaw) * .12, Math.abs(yMaxRaw || 1) * .02, .001);
    const xMin = xMinRaw - xPad;
    const xMax = xMaxRaw + xPad;
    const yMin = yMinRaw - yPad;
    const yMax = yMaxRaw + yPad;
    const x = (value) => left + (value - xMin) / (xMax - xMin) * (720 - left - right);
    const y = (value) => top + (yMax - value) / (yMax - yMin) * (430 - top - bottom);
    for (let index = 0; index <= 4; index += 1) {
      const xv = xMin + (xMax - xMin) * index / 4;
      const yv = yMin + (yMax - yMin) * index / 4;
      const px = x(xv);
      const py = y(yv);
      svg.appendChild(svgNode("line", { x1: px, x2: px, y1: top, y2: 430 - bottom, class: "gridline" }));
      svg.appendChild(svgNode("line", { x1: left, x2: 720 - right, y1: py, y2: py, class: "gridline" }));
      svg.appendChild(svgNode("text", { x: px, y: 430 - bottom + 18, "text-anchor": "middle", class: "axis-label" }, format(xv)));
      svg.appendChild(svgNode("text", { x: left - 9, y: py + 3, "text-anchor": "end", class: "axis-label" }, format(yv)));
    }
    svg.appendChild(svgNode("line", { x1: left, x2: 720 - right, y1: 430 - bottom, y2: 430 - bottom, class: "axis" }));
    svg.appendChild(svgNode("line", { x1: left, x2: left, y1: top, y2: 430 - bottom, class: "axis" }));
    points.forEach((point) => {
      const circle = svgNode("circle", {
        cx: x(point.x), cy: y(point.y), r: point.split === "heldout" ? 6.3 : 5.2,
        fill: point.split === "heldout" ? "#6ea8ff" : "#ffca72",
        stroke: "rgba(255,255,255,.35)", "stroke-width": 1.2, class: "tooltip-target",
      });
      titleFor(circle, `${strategyLabel(point.row)}\n${xMetric}: ${format(point.x)}\n${yMetric}: ${format(point.y)}\n${point.split}`);
      svg.appendChild(circle);
    });
    svg.appendChild(svgNode("text", { x: (left + 720 - right) / 2, y: 418, "text-anchor": "middle", class: "axis-label" }, short(xMetric, 70)));
    const yLabel = svgNode("text", { x: 15, y: (top + 430 - bottom) / 2, transform: `rotate(-90 15 ${(top + 430 - bottom) / 2})`, "text-anchor": "middle", class: "axis-label" }, short(yMetric, 50));
    svg.appendChild(yLabel);
  }

  function promotionDecision(row) {
    const record = parseRecord(row.decision_record);
    const review = record.review && typeof record.review === "object" ? record.review : {};
    return {
      id: String(row.decision ?? record.decision_id ?? "decision"),
      status: String(record.decision ?? record.status ?? row.decision_status ?? "reviewed").toLowerCase(),
      at: String(review.reviewed_at_utc ?? record.reviewed_at_utc ?? record.decided_at_utc ?? record.created_at_utc ?? ""),
      version: record.version ?? "",
      experiment: String(row.experiment ?? ""),
      active: String(row.active_pointer ?? ""),
      fill: String(row.fill_preset ?? ""),
      retrieval: String(row.retrieval_preset ?? ""),
    };
  }

  function drawPromotions() {
    const svg = $("promotion-chart");
    const decisions = new Map();
    (state.rows[views.promotions] || []).forEach((row) => {
      const item = promotionDecision(row);
      if (!decisions.has(item.id)) decisions.set(item.id, item);
    });
    const rows = [...decisions.values()].sort((left, right) => left.at.localeCompare(right.at) || left.id.localeCompare(right.id));
    if (!rows.length) {
      emptyChart(svg, "No promotion decisions", "Reviewed decisions appear here; experiments are never auto-promoted.");
      return;
    }
    clearSvg(svg);
    const left = 54;
    const right = 42;
    const centerY = 210;
    svg.appendChild(svgNode("line", { x1: left, x2: 720 - right, y1: centerY, y2: centerY, stroke: "rgba(178,214,213,.3)", "stroke-width": 2 }));
    const step = rows.length === 1 ? 0 : (720 - left - right) / (rows.length - 1);
    rows.forEach((row, index) => {
      const x = rows.length === 1 ? 360 : left + index * step;
      const above = index % 2 === 0;
      const labelY = above ? 98 : 323;
      const statusColor = row.status.includes("promot") ? "#a7ed68" : row.status.includes("reject") ? "#ff806e" : "#ffca72";
      svg.appendChild(svgNode("line", { x1: x, x2: x, y1: centerY, y2: above ? labelY + 34 : labelY - 24, stroke: "rgba(178,214,213,.24)", "stroke-width": 1 }));
      const circle = svgNode("circle", { cx: x, cy: centerY, r: 8, fill: statusColor, stroke: "#0d2024", "stroke-width": 4 });
      titleFor(circle, `${row.id}\n${row.status}\n${row.experiment}\n${row.fill} + ${row.retrieval}`);
      svg.appendChild(circle);
      svg.appendChild(svgNode("text", { x, y: labelY, "text-anchor": "middle", "font-size": 10, "font-weight": 780, fill: statusColor }, row.status.toUpperCase()));
      svg.appendChild(svgNode("text", { x, y: labelY + 15, "text-anchor": "middle", "font-size": 9 }, short(row.id, 20)));
      svg.appendChild(svgNode("text", { x, y: labelY + 28, "text-anchor": "middle", class: "axis-label" }, row.at ? row.at.slice(0, 10) : `version ${row.version || "—"}`));
    });
    svg.appendChild(svgNode("text", { x: 360, y: 402, "text-anchor": "middle", class: "axis-label" }, "A reviewed pointer is research state only; activation outside this graph remains explicit."));
  }

  function filteredLineups() {
    const slate = $("network-slate").value;
    const winnersOnly = $("winner-only").checked;
    const grouped = new Map();
    (state.rows[views.structure] || []).forEach((row) => {
      if (slate !== "__all__" && String(row.slate_id) !== slate) return;
      const winner = row.is_winner === true || String(row.lineup_kind) === "WinningLineup";
      if (winnersOnly && !winner) return;
      const id = String(row.lineup ?? "");
      if (!id) return;
      if (!grouped.has(id)) grouped.set(id, { id, winner, slate: String(row.slate_id ?? ""), score: row.score_present === true ? finite(row.score) : null });
    });
    return [...grouped.values()].sort((left, right) => Number(right.winner) - Number(left.winner) || (right.score ?? -Infinity) - (left.score ?? -Infinity) || left.id.localeCompare(right.id));
  }

  function refreshNetworkLineups() {
    const select = $("network-lineup");
    const lineups = filteredLineups();
    const preferred = lineups.some((lineup) => lineup.id === state.selectedLineup) ? state.selectedLineup : lineups[0]?.id ?? "";
    setOptions(select, lineups.map((lineup) => ({
      value: lineup.id,
      label: `${lineup.winner ? "★ " : ""}${short(lineup.id, 29)}${lineup.score === null ? "" : ` · ${format(lineup.score)}`}`,
    })), preferred);
    state.selectedLineup = select.value;
    drawNetwork();
  }

  function networkLabel(record, fallback) {
    return String(record.display_name ?? record.name ?? record.team ?? record.abbreviation ?? fallback);
  }

  function drawNetwork() {
    const svg = $("network-chart");
    const lineupId = $("network-lineup").value;
    state.selectedLineup = lineupId;
    const rows = (state.rows[views.structure] || []).filter((row) => String(row.lineup) === lineupId);
    const body = $("roster-body");
    const summary = $("lineup-summary");
    body.replaceChildren();
    summary.replaceChildren();
    if (!rows.length) {
      emptyChart(svg, "No lineup selected", "Choose a slate and lineup to traverse its graph neighborhood.");
      const paragraph = document.createElement("p");
      paragraph.textContent = "No structural rows are available for this filter.";
      summary.appendChild(paragraph);
      return;
    }
    clearSvg(svg);
    const first = rows[0];
    const isWinner = first.is_winner === true || String(first.lineup_kind) === "WinningLineup";
    const heading = document.createElement("h3");
    heading.textContent = short(lineupId, 42);
    if (isWinner) {
      const badge = document.createElement("span");
      badge.className = "winner-badge";
      badge.textContent = "Winner";
      heading.appendChild(badge);
    }
    summary.appendChild(heading);
    const metadata = document.createElement("p");
    metadata.textContent = `${first.slate_id ?? "Unknown slate"}${first.score_present === true && finite(first.score) !== null ? ` · score ${format(first.score)}` : " · score not retained"}`;
    summary.appendChild(metadata);
    const provenanceRows = uniq(rows.filter((row) => row.corpus_snapshot || row.producing_fill_preset).map((row) => `${row.corpus_snapshot ?? "—"}\u0000${row.producing_fill_preset ?? "—"}`));
    if (provenanceRows.length) {
      const provenance = document.createElement("p");
      const [snapshot, fill] = provenanceRows[0].split("\u0000");
      provenance.textContent = `Corpus ${short(snapshot, 24)} · fill ${short(fill, 24)}${provenanceRows.length > 1 ? ` · ${provenanceRows.length} snapshot memberships` : ""}`;
      summary.appendChild(provenance);
    }
    const count = document.createElement("p");
    const uniqueRosterCount = new Set(rows.map((row) => `${row.player}\u0000${row.team_slate}\u0000${row.game}`)).size;
    count.textContent = `${uniqueRosterCount} roster relationships · receipt-bound structural projection`;
    summary.appendChild(count);

    const playerRows = new Map();
    rows.forEach((row) => {
      const key = `${row.player}\u0000${row.team_slate}\u0000${row.game}`;
      if (!playerRows.has(key)) playerRows.set(key, row);
    });
    const players = [...playerRows.values()].map((row) => ({
      id: String(row.player), label: networkLabel(parseRecord(row.player_record), short(row.player, 20)),
      team: String(row.team_slate), game: String(row.game), row,
    })).sort((left, right) => left.label.localeCompare(right.label));
    const teams = uniq(players.map((player) => player.team)).sort();
    const games = uniq(players.map((player) => player.game)).sort();
    const playerY = new Map();
    players.forEach((player, index) => playerY.set(player.id, 65 + (410 / Math.max(1, players.length - 1)) * index));
    const teamY = new Map();
    teams.forEach((team) => teamY.set(team, mean(players.filter((player) => player.team === team).map((player) => playerY.get(player.id))) ?? 270));
    const gameY = new Map();
    games.forEach((game) => gameY.set(game, mean(players.filter((player) => player.game === game).map((player) => teamY.get(player.team))) ?? 270));

    const lineupX = 88;
    const playerX = 325;
    const teamX = 600;
    const gameX = 825;
    svg.appendChild(svgNode("text", { x: lineupX, y: 28, "text-anchor": "middle", class: "axis-label", "font-weight": 800 }, "LINEUP"));
    svg.appendChild(svgNode("text", { x: playerX, y: 28, "text-anchor": "middle", class: "axis-label", "font-weight": 800 }, "PLAYER"));
    svg.appendChild(svgNode("text", { x: teamX, y: 28, "text-anchor": "middle", class: "axis-label", "font-weight": 800 }, "TEAM"));
    svg.appendChild(svgNode("text", { x: gameX, y: 28, "text-anchor": "middle", class: "axis-label", "font-weight": 800 }, "GAME"));

    players.forEach((player) => {
      const py = playerY.get(player.id);
      const ty = teamY.get(player.team);
      const gy = gameY.get(player.game);
      svg.appendChild(svgNode("path", { d: `M 154 270 C 210 270, 245 ${py}, ${playerX - 12} ${py}`, fill: "none", stroke: "rgba(103,224,193,.25)", "stroke-width": 1.4 }));
      svg.appendChild(svgNode("path", { d: `M ${playerX + 12} ${py} C 420 ${py}, 500 ${ty}, ${teamX - 48} ${ty}`, fill: "none", stroke: "rgba(110,168,255,.22)", "stroke-width": 1.3 }));
      svg.appendChild(svgNode("path", { d: `M ${teamX + 48} ${ty} C 690 ${ty}, 735 ${gy}, ${gameX - 55} ${gy}`, fill: "none", stroke: "rgba(255,202,114,.2)", "stroke-width": 1.2 }));
    });

    const lineup = svgNode("g", { class: "tooltip-target" });
    lineup.appendChild(svgNode("rect", { x: 22, y: 245, width: 132, height: 50, rx: 12, fill: isWinner ? "#ffca72" : "#67e0c1", "fill-opacity": .9 }));
    lineup.appendChild(svgNode("text", { x: 88, y: 267, "text-anchor": "middle", fill: "#071316", "font-size": 10, "font-weight": 850 }, isWinner ? "WINNING LINEUP" : "LINEUP"));
    lineup.appendChild(svgNode("text", { x: 88, y: 282, "text-anchor": "middle", fill: "#071316", "font-size": 8.5 }, short(lineupId, 20)));
    titleFor(lineup, lineupId);
    svg.appendChild(lineup);

    players.forEach((player) => {
      const py = playerY.get(player.id);
      const circle = svgNode("circle", { cx: playerX, cy: py, r: 8, fill: "#67e0c1", stroke: "#0d2024", "stroke-width": 3 });
      titleFor(circle, `${player.label}\n${player.id}`);
      svg.appendChild(circle);
      svg.appendChild(svgNode("text", { x: playerX + 14, y: py + 3, "font-size": 9.5 }, short(player.label, 24)));
      const tr = document.createElement("tr");
      [player.label, short(player.team, 20), short(player.game, 20)].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    teams.forEach((team) => {
      const ty = teamY.get(team);
      const group = svgNode("g", { class: "tooltip-target" });
      group.appendChild(svgNode("rect", { x: teamX - 48, y: ty - 15, width: 96, height: 30, rx: 8, fill: "#173b4f", stroke: "#6ea8ff", "stroke-opacity": .65 }));
      group.appendChild(svgNode("text", { x: teamX, y: ty + 3, "text-anchor": "middle", "font-size": 9.5, "font-weight": 720 }, short(team, 17)));
      titleFor(group, team);
      svg.appendChild(group);
    });
    games.forEach((game) => {
      const gy = gameY.get(game);
      const group = svgNode("g", { class: "tooltip-target" });
      group.appendChild(svgNode("rect", { x: gameX - 55, y: gy - 17, width: 110, height: 34, rx: 9, fill: "#2c2719", stroke: "#ffca72", "stroke-opacity": .65 }));
      group.appendChild(svgNode("text", { x: gameX, y: gy + 3, "text-anchor": "middle", "font-size": 9.2, "font-weight": 720 }, short(game, 18)));
      titleFor(group, game);
      svg.appendChild(group);
    });
  }

  function renderMetadata(status, projection) {
    $("meta-registry").textContent = String(status.registry_id ?? "—");
    $("meta-time").textContent = String(status.generated_at_utc ?? "—").replace("T", " ").replace("Z", " UTC");
    const counts = status.view_row_counts || {};
    $("meta-rows").textContent = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0).toLocaleString();
    const winnerIds = new Set((state.rows[views.structure] || []).filter((row) => row.is_winner === true || String(row.lineup_kind) === "WinningLineup").map((row) => String(row.lineup)));
    $("meta-winners").textContent = winnerIds.size ? `${winnerIds.size} licensed` : "not loaded";
    $("meta-hash").textContent = String(projection.projection_sha256 ?? "—").slice(0, 18);
    $("meta-hash").title = String(projection.projection_sha256 ?? "");
  }

  function renderAll() {
    populateControls();
    drawPresetCatalog();
    drawLineage();
    drawHeatmap();
    drawPaired();
    drawScatter();
    drawPromotions();
    drawNetwork();
  }

  function bindEvents() {
    $("lineage-slate").addEventListener("change", drawLineage);
    $("heat-metric").addEventListener("change", drawHeatmap);
    $("heat-split").addEventListener("change", drawHeatmap);
    $("paired-metric").addEventListener("change", drawPaired);
    $("scatter-x").addEventListener("change", drawScatter);
    $("scatter-y").addEventListener("change", drawScatter);
    $("network-slate").addEventListener("change", refreshNetworkLineups);
    $("winner-only").addEventListener("change", refreshNetworkLineups);
    $("network-lineup").addEventListener("change", drawNetwork);
  }

  async function load() {
    bindEvents();
    const notReady = $("not-ready");
    const message = $("not-ready-message");
    try {
      const response = await fetch("/api/corpus-research/projection", { headers: { Accept: "application/json" }, cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || !payload.projection) {
        message.textContent = payload.message || "The receipt-bound graph projection is not ready.";
        return;
      }
      state.projection = payload.projection;
      state.rows = payload.projection.views || {};
      renderMetadata(payload.status || {}, payload.projection);
      renderAll();
      notReady.hidden = true;
      $("research-content").hidden = false;
    } catch (_) {
      message.textContent = "The read-only corpus projection could not be reached. No partial or unverified data is shown.";
    }
  }

  document.addEventListener("DOMContentLoaded", load);
})();
