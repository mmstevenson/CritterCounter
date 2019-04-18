var map;

function onEachFeature(feature, layer) {
  if (feature.properties) {
    label = feature.properties.label
    confidence = feature.properties.probability*100
    layer.bindPopup('Species: ' + label + '<br>' +
                    'Confidence: ' + confidence.toString().substr(0,4) +'%');}}

function initializePage(){
  var geojsonMarkerOptions = {
    radius: 4,
    fillColor: "Turquoise",
    color: "#000",
    weight: 1,
    opacity: 1,
    fillOpacity: 1.0
  };

  map = L.map("map").setView([47.420316, -120.350371], 7);
  L.tileLayer(
    "https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw",
    {
      maxZoom: 18,
      attribution:
        'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, ' +
          '<a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, ' +
          'Imagery © <a href="http://mapbox.com">Mapbox</a>',
      id: "mapbox.light"
    }
  ).addTo(map);

  var heatAll = new L.HeatLayer(speciesAll, {radius:16,blur:25,maxZoom:11,minOpacity:0.25,}).addTo(map);
  var heatBears = new L.HeatLayer(bears, {radius:16,blur:25,maxZoom:11,minOpacity:0.25});
  var heatDeer = new L.HeatLayer(elkDeer, {radius:16,blur:25,maxZoom:11,minOpacity:0.25});
  var heatCoyotes = new L.HeatLayer(coyotes, {radius:16,blur:25,maxZoom:11,minOpacity:0.25});
  var heatCats = new L.HeatLayer(cats, {radius:16,blur:25,maxZoom:11,minOpacity:0.25});

  var baseMaps = {
    "All Species": heatAll,
    "Bears": heatBears,
    "Deer & Elk": heatDeer,
    "Coyotes": heatCoyotes,
    "Bobcats & Cougars": heatCats
  };

  var userPoints = L.geoJSON(mapData, {
      pointToLayer: function (feature, latlng) {return L.circleMarker(latlng, geojsonMarkerOptions);
    },
    onEachFeature: onEachFeature
  }).addTo(map);

  var overlayMap = {
    "User Images": userPoints
  };

  L.control.layers(baseMaps, overlayMap).addTo(map);
};
initializePage();
