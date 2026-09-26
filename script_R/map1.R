library(dplyr)
library(leaflet)

a1 <- phenotype_c1 |> 
  distinct(YEAR_x, LONGITUDE, LATITUDE)

leaflet(a1) |>
  addProviderTiles(providers$Esri.WorldImagery) |>
  addCircleMarkers(
    lng = ~LONGITUDE,
    lat = ~LATITUDE,
    radius = 5,
    color = "red",
    fillColor = "red",
    fillOpacity = 0.8,
    stroke = FALSE,
    popup = ~paste0(
      "<b>Year:</b> ", YEAR_x,
      "<br><b>Latitude:</b> ", LATITUDE,
      "<br><b>Longitude:</b> ", LONGITUDE
    )
  )


a1 <- phenotype_c1 |>
  # filter(YEAR_x == 2000) |> 
  group_by(LONGITUDE, LATITUDE) |>
  summarise(Y = mean(YLD_BE, na.rm = TRUE), .groups = "drop")

pal <- colorNumeric(palette = c("blue", "yellow", "red"),
                    domain = a1$Y)

leaflet(a1) |>
  addProviderTiles(providers$Esri.WorldImagery) |>
  addCircleMarkers(
    lng = ~ LONGITUDE,
    lat = ~ LATITUDE,
    fillColor = ~ pal(Y),
    radius = 5,
    fillOpacity = 0.8,
    stroke = FALSE,
    popup = ~ paste0(
      "<b>Yield:</b> ",
      round(Y, 2),
      "<br><b>Latitude:</b> ",
      LATITUDE,
      "<br><b>Longitude:</b> ",
      LONGITUDE
    )
  ) |>
  addLegend(
    "bottomright",
    pal = pal,
    values = ~ Y,
    title = "Yield",
    opacity = 1
  )



a1 <- phenotype_c1 |> 
  filter(YEAR_x == 2000) |> 
  distinct(LONGITUDE, LATITUDE)

leaflet(a1) |>
  addProviderTiles(providers$Esri.WorldImagery) |>
  addCircleMarkers(
    lng = ~LONGITUDE,
    lat = ~LATITUDE,
    radius = 5,
    color = "red",
    fillColor = "red",
    fillOpacity = 1,
    stroke = FALSE,
    popup = ~paste0(
      "<br><b>Latitude:</b> ", LATITUDE,
      "<br><b>Longitude:</b> ", LONGITUDE
    )
  )



tbl = table(phenotype_c1$LOC, phenotype_c1$YEAR_x)

colSums(tbl>0)
