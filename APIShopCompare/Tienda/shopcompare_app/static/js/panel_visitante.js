const data = [
{
"descripcion": "Arroz blanco de primera calidad, sin conservadores.",
"precio": 25.5,
"producto": "Arroz Extra Grano Largo 1kg",
"sucursal": "Sucursal Centro",
"tienda": "Walmart"
},
{
"descripcion": "Arroz blanco de primera calidad, sin conservadores.",
"precio": 22.9,
"producto": "Arroz Extra Grano Largo 1kg",
"sucursal": "Sucursal Norte",
"tienda": "Soriana"
},
{
"descripcion": "Arroz blanco de primera calidad, sin conservadores.",
"precio": 19.99,
"producto": "Arroz Extra Grano Largo 1kg",
"sucursal": "Sucursal Sur",
"tienda": "Bodega Aurrera"
}
];

document.getElementById("json").textContent =
JSON.stringify(data,null,4);
