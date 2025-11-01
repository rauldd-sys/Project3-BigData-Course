/* global use, db */
// MongoDB Playground script for covid_data.encounters collection
// Data ingestion (run from shell once):
//   jq -c '.records[]' Project3/data/health_data.json > Project3/data/encounters.ndjson
//   mongoimport --db covid_data --collection encounters --drop --file Project3/data/encounters.ndjson

use('covid_data');

console.log('--- Dataset Quick Scan ---');
const sampleDocs = db.encounters.aggregate([
  { $sample: { size: 3 } },
  {
    $project: {
      _id: 0,
      dateRep: 1,
      day: 1,
      month: 1,
      year: 1,
      cases: 1,
      deaths: 1,
      countriesAndTerritories: 1,
      geoId: 1,
      popData2019: 1,
      continentExp: 1,
      cumulative14d: '$Cumulative_number_for_14_days_of_COVID-19_cases_per_100000'
    }
  }
]).toArray();
printjson(sampleDocs);

const totalDocs = db.encounters.countDocuments();
console.log('Total encounters:', totalDocs);

console.log('\n--- Field Completeness Overview ---');
const completeness = db.encounters.aggregate([
  {
    $project: {
      has_cases: { $cond: [{ $ifNull: ['$cases', false] }, 1, 0] },
      has_deaths: { $cond: [{ $ifNull: ['$deaths', false] }, 1, 0] },
      has_country: { $cond: [{ $ifNull: ['$countriesAndTerritories', false] }, 1, 0] },
      has_geo: { $cond: [{ $ifNull: ['$geoId', false] }, 1, 0] },
      has_population: { $cond: [{ $ifNull: ['$popData2019', false] }, 1, 0] },
      has_continent: { $cond: [{ $ifNull: ['$continentExp', false] }, 1, 0] },
      has_date: { $cond: [{ $ifNull: ['$dateRep', false] }, 1, 0] }
    }
  },
  {
    $group: {
      _id: null,
      records: { $sum: 1 },
      cases: { $avg: '$has_cases' },
      deaths: { $avg: '$has_deaths' },
      country: { $avg: '$has_country' },
      geo: { $avg: '$has_geo' },
      population: { $avg: '$has_population' },
      continent: { $avg: '$has_continent' },
      date: { $avg: '$has_date' }
    }
  },
  {
    $project: {
      _id: 0,
      records: 1,
      fields: {
        cases: { $round: [{ $multiply: ['$cases', 100] }, 2] },
        deaths: { $round: [{ $multiply: ['$deaths', 100] }, 2] },
        country: { $round: [{ $multiply: ['$country', 100] }, 2] },
        geo: { $round: [{ $multiply: ['$geo', 100] }, 2] },
        population: { $round: [{ $multiply: ['$population', 100] }, 2] },
        continent: { $round: [{ $multiply: ['$continent', 100] }, 2] },
        date: { $round: [{ $multiply: ['$date', 100] }, 2] }
      }
    }
  }
]).next();
printjson(completeness);

console.log('\n--- High-Level Metrics (Aggregation Pipelines) ---');
const topCountriesByCases = db.encounters.aggregate([
  {
    $group: {
      _id: '$countriesAndTerritories',
      total_cases: { $sum: '$cases' },
      total_deaths: { $sum: '$deaths' },
      population: { $max: '$popData2019' },
      latest_continent: { $max: '$continentExp' }
    }
  },
  {
    $addFields: {
      case_fatality_rate: {
        $cond: [
          { $gt: ['$total_cases', 0] },
          { $round: [{ $multiply: [{ $divide: ['$total_deaths', '$total_cases'] }, 100] }, 2] },
          null
        ]
      },
      cases_per_100k: {
        $cond: [
          { $gt: ['$population', 0] },
          {
            $round: [
              { $multiply: [{ $divide: ['$total_cases', '$population'] }, 100000] },
              2
            ]
          },
          null
        ]
      }
    }
  },
  { $sort: { total_cases: -1 } },
  { $limit: 15 }
]).toArray();
console.log('Top 15 countries by confirmed cases:');
printjson(topCountriesByCases);

const continentTrends = db.encounters.aggregate([
  {
    $group: {
      _id: { continent: '$continentExp', year: '$year' },
      cases: { $sum: '$cases' },
      deaths: { $sum: '$deaths' }
    }
  },
  {
    $group: {
      _id: '$_id.continent',
      yearly: {
        $push: {
          year: '$_id.year',
          cases: '$cases',
          deaths: '$deaths'
        }
      }
    }
  },
  { $sort: { _id: 1 } }
]).toArray();
console.log('Yearly totals per continent (for area/line charts):');
printjson(continentTrends);

const monthlyGlobalTrend = db.encounters.aggregate([
  {
    $group: {
      _id: { year: '$year', month: '$month' },
      cases: { $sum: '$cases' },
      deaths: { $sum: '$deaths' }
    }
  },
  { $sort: { '_id.year': 1, '_id.month': 1 } }
]).toArray();
console.log('Monthly global cases/deaths:');
printjson(monthlyGlobalTrend);

console.log('\n--- MapReduce Jobs (MongoDB MR equivalent to Hadoop jobs) ---');
// MR Job 1: Total cases/deaths per country (overall totals)
const mapCountryTotals = function () {
  emit(this.countriesAndTerritories || 'Unknown', {
    cases: this.cases || 0,
    deaths: this.deaths || 0
  });
};

const reduceCountryTotals = function (key, values) {
  var accumulator = { cases: 0, deaths: 0 };
  values.forEach(function (value) {
    accumulator.cases += value.cases;
    accumulator.deaths += value.deaths;
  });
  return accumulator;
};

var startCountryTotals = new Date();
const mrCountryTotals = db.encounters.mapReduce(mapCountryTotals, reduceCountryTotals, {
  out: { inline: 1 }
});
var elapsedCountryTotals = new Date() - startCountryTotals;
console.log('mongoMR:countryTotals runtime (ms):', elapsedCountryTotals);
printjson(mrCountryTotals.results.slice(0, 10));

// MR Job 2: Peak 14-day rolling sum per country (to mimic sliding window)
const mapRolling = function () {
  if (this.countriesAndTerritories && this.cases && this.dateRep) {
    emit(this.countriesAndTerritories, [
      { date: this.dateRep, cases: this.cases }
    ]);
  }
};

const reduceRolling = function (key, values) {
  var merged = [];
  values.forEach(function (list) {
    merged = merged.concat(list);
  });
  return merged;
};

const finalizeRolling = function (key, entries) {
  var sorted = entries
    .map(function (entry) {
      var parts = entry.date.split('/');
      // dateRep format: DD/MM/YYYY
      var iso = parts[2] + '-' + parts[1] + '-' + parts[0];
      return {
        date: new Date(iso),
        cases: entry.cases
      };
    })
    .sort(function (a, b) {
      return a.date - b.date;
    });

  var peak = 0;
  for (var i = 0; i < sorted.length; i++) {
    var windowSum = 0;
    for (var j = Math.max(0, i - 13); j <= i; j++) {
      windowSum += sorted[j].cases;
    }
    if (windowSum > peak) {
      peak = windowSum;
    }
  }
  return { peakRolling14: peak };
};

var startRolling = new Date();
const mrRolling = db.encounters.mapReduce(mapRolling, reduceRolling, {
  finalize: finalizeRolling,
  out: { inline: 1 }
});
var elapsedRolling = new Date() - startRolling;
console.log('mongoMR:peakRolling14 runtime (ms):', elapsedRolling);

const topRolling = mrRolling.results
  .sort((a, b) => b.value.peakRolling14 - a.value.peakRolling14)
  .slice(0, 10);
console.log('Top 10 countries by peak 14-day rolling cases:');
printjson(topRolling);

console.log('\n--- Visualization Export Snapshot ---');
if (db.getCollectionNames().indexOf('analytics') !== -1) {
  db.analytics.drop();
}
const analyticsDocs = [
  { metric: 'topCountriesByCases', updatedAt: new Date(), payload: topCountriesByCases },
  { metric: 'continentTrends', updatedAt: new Date(), payload: continentTrends },
  { metric: 'monthlyGlobalTrend', updatedAt: new Date(), payload: monthlyGlobalTrend },
  { metric: 'peakRolling14', updatedAt: new Date(), payload: topRolling }
];
if (analyticsDocs.every(function (doc) { return doc.payload && doc.payload.length !== undefined ? doc.payload.length > 0 : true; })) {
  db.analytics.insertMany(analyticsDocs);
  console.log('Analytics persisted to `analytics` collection for BI/visualization. Document count:', db.analytics.countDocuments());
} else {
  console.log('Skipped analytics export because one or more payloads were empty.');
}