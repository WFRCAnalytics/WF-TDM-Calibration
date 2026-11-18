-- {{< year >}}: the current year, evaluated when the page is rendered.
return { ['year'] = function() return pandoc.Str(os.date('%Y')) end }
