/* GeoSupply OSINT — MapLibre world map with toggleable intel layers */
"use strict";

const OsintMap = (() => {
  let map = null;
  const visible = { conflict: true, earthquake: true, disaster: true, chokepoint: true, port: true };

  const BASE_STYLE = {
    version: 8,
    sources: {
      carto: {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors © CARTO",
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#04070b" } },
      { id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 0.85 } },
    ],
  };

  function fc(features) { return { type: "FeatureCollection", features }; }

  function eventFeature(e) {
    return {
      type: "Feature",
      geometry: { type: "Point", coordinates: [e.lon, e.lat] },
      properties: {
        title: e.title, summary: e.summary, source: e.source,
        url: e.url, severity: e.severity, ts: e.ts, category: e.category,
      },
    };
  }

  function init() {
    map = new maplibregl.Map({
      container: "map",
      style: BASE_STYLE,
      center: [55, 18],
      zoom: 2.1,
      minZoom: 1.2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    map.on("load", () => {
      for (const id of ["conflict", "earthquake", "disaster", "chokepoint", "port"]) {
        map.addSource(id, { type: "geojson", data: fc([]) });
      }

      map.addLayer({
        id: "conflict", type: "circle", source: "conflict",
        paint: {
          "circle-color": "#ef4444",
          "circle-opacity": 0.55,
          "circle-radius": ["interpolate", ["linear"], ["get", "severity"], 0, 3, 10, 13],
          "circle-stroke-color": "#ef4444",
          "circle-stroke-width": 1,
          "circle-stroke-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "earthquake", type: "circle", source: "earthquake",
        paint: {
          "circle-color": "#fbbf24",
          "circle-opacity": 0.5,
          "circle-radius": ["interpolate", ["linear"], ["get", "severity"], 2, 3, 8, 14],
          "circle-stroke-color": "#fbbf24",
          "circle-stroke-width": 1,
        },
      });
      map.addLayer({
        id: "disaster", type: "circle", source: "disaster",
        paint: {
          "circle-color": "#a78bfa",
          "circle-opacity": 0.55,
          "circle-radius": ["interpolate", ["linear"], ["get", "severity"], 0, 3, 10, 10],
          "circle-stroke-color": "#a78bfa",
          "circle-stroke-width": 1,
        },
      });
      map.addLayer({
        id: "chokepoint", type: "circle", source: "chokepoint",
        paint: {
          "circle-color": ["get", "color"],
          "circle-opacity": 0.35,
          "circle-radius": ["+", 7, ["*", 9, ["get", "stress"]]],
          "circle-stroke-color": ["get", "color"],
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "port", type: "circle", source: "port",
        paint: {
          "circle-color": ["match", ["get", "status"],
            "DISRUPTED", "#ef4444", "WATCH", "#fbbf24", "#38bdf8"],
          "circle-opacity": 0.8,
          "circle-radius": 4,
          "circle-stroke-color": "#0b1118",
          "circle-stroke-width": 1,
        },
      });

      for (const id of ["conflict", "earthquake", "disaster", "chokepoint", "port"]) {
        map.on("click", id, onClick);
        map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
      }
    });

    document.querySelectorAll(".lchip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const layer = btn.dataset.layer;
        visible[layer] = !visible[layer];
        btn.classList.toggle("active", visible[layer]);
        if (map.getLayer(layer)) {
          map.setLayoutProperty(layer, "visibility", visible[layer] ? "visible" : "none");
        }
      });
    });
  }

  function onClick(evt) {
    const f = evt.features && evt.features[0];
    if (!f) return;
    const p = f.properties;
    const link = p.url && p.url.startsWith("http")
      ? `<div><a class="pop-link" href="${Util.esc(p.url)}" target="_blank" rel="noopener">source ↗</a></div>` : "";
    const meta = p.category === "chokepoint"
      ? `stress ${(p.stress * 100).toFixed(0)}% · ${p.events} events · ~${p.transits} transits/day`
      : Util.esc(p.source || "") + (p.ts ? ` · ${Util.age(p.ts)} ago` : "");
    new maplibregl.Popup({ closeButton: true })
      .setLngLat(evt.lngLat)
      .setHTML(
        `<div class="pop-title">${Util.esc(p.title)}</div>` +
        (p.summary && p.summary !== p.title ? `<div>${Util.esc(p.summary)}</div>` : "") +
        `<div class="pop-meta">${meta}</div>${link}`
      )
      .addTo(map);
  }

  function setData(snap) {
    if (!map || !map.isStyleLoaded()) {
      // style still loading — retry once it's ready
      if (map) map.once("idle", () => setData(snap));
      return;
    }
    const byCat = { conflict: [], earthquake: [], disaster: [] };
    for (const e of snap.events || []) {
      if (byCat[e.category]) byCat[e.category].push(eventFeature(e));
    }
    for (const [cat, feats] of Object.entries(byCat)) {
      map.getSource(cat)?.setData(fc(feats));
    }
    map.getSource("chokepoint")?.setData(fc((snap.chokepoints || []).map((c) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [c.lon, c.lat] },
      properties: {
        title: c.name, summary: c.description, category: "chokepoint",
        stress: c.stress_index, level: c.level, events: c.recent_events,
        transits: c.daily_transits, color: Util.stressColor(c.level),
      },
    }))));
    map.getSource("port")?.setData(fc((snap.india_ports || []).map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        title: `${p.name} Port`, summary: p.note || `${p.state} — ${p.status}`,
        source: "Open-Meteo", status: p.status, category: "port",
      },
    }))));

    const counts = [
      `CONFLICT ${byCat.conflict.length}`,
      `SEISMIC ${byCat.earthquake.length}`,
      `DISASTER ${byCat.disaster.length}`,
    ].join("  ·  ");
    document.getElementById("map-counts").textContent = counts;
  }

  return { init, setData };
})();
