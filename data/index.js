const fs = require('fs');
const geojson = JSON.parse(fs.readFileSync(process.argv[2]).toString());
const id=geojson.features[0].properties.id;
const cid=geojson.features[0].properties['c:id'];
const datetime = geojson.features[0].properties.datetime.split('-')[0];
console.log(`${datetime}\t${cid}\t${id}`);


