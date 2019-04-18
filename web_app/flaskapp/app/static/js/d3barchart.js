console.log(chartData);

var width = 280,
    barHeight = 30,
    labelWidth = 80;

var x = d3.scaleLinear()
    .range([0, width - labelWidth])
    .domain([0, d3.max(chartData.map(function(d){return d.count;}))]);

var chart = d3.select(".chart");

var groupspace = 20;

// chart.attr("height", barHeight * (chartData.length + groupspace));

var bars = chart.selectAll()
  .data(chartData)
  .enter().append("g")
  .attr("transform", function(d, i) { return "translate(" + labelWidth + "," + i * (barHeight + groupspace) + ")"; });

bars.append("rect")
  .attr("class", "thing")
  .attr("width", 0)
  .attr("height", barHeight - 1)
  .transition()
    .duration(1500)
    .attr("width", function(d) { return x(d.count); });

bars.append("text")
  .attr("class", "value")
  .attr("x", function(d) {
    if(x(d.count)<12){
      return x(d.count) + 8;
    } else {return x(d.count) - 3;}})
  .attr("y", barHeight / 2)
  .attr("dy", ".35em")
  .text(function(d) { return d.count; });

bars.append("text")
  .attr("class", "label")
  .attr("x", -6)
  .attr("y", barHeight/2)
  .attr("dy", ".35em")
  .text(function(d) { return d.name; });
