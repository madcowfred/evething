function drawChart() {
  $.getJSON( "single/data/?" + $.param(parseQueryString()), function( rawData ) {
    var i, c, row, charOrder = [];

    var charLastBalance = {};
    for(i=0; i<rawData.length; i++) {
        row = rawData[i];

        if (charOrder.indexOf(row[2]) < 0) {
            charLastBalance[row[2]] = undefined;
            charOrder[charOrder.length] = row[2];
        }
    };

    var chartData = new google.visualization.DataTable();
    // Date, char 1, char 2, char 3, ...
    chartData.addColumn('date', 'Timestamp');

    // Add all character columns by charOrder
    for (c=0; c<charOrder.length; c++) {
        chartData.addColumn('number', charOrder[c]);
    }

    var charIndex, chartRow = [];
    for (var i=0; i<rawData.length; i++) {
        row = rawData[i]

        // Since this row has data, it is the most recent data value for
        //   the current character
        charLastBalance[row[2]] = row[1];

        // Add the Date row
        chartRow[0] = new Date(row[0] + "+00:00");

        for (c=0; c<charOrder.length; c++) {
            chartRow[c + 1] = parseFloat(charLastBalance[charOrder[c]]);
        }

        chartData.addRow(chartRow);
    }

    var chart = new google.visualization.AnnotationChart(document.getElementById('chart_div'));
    chart.draw(chartData,{});
});
}