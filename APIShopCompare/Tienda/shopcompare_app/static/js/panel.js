function openModal(id){
    document.getElementById(id).classList.add("active");
}

function closeModal(id){
    document.getElementById(id).classList.remove("active");
}

window.onclick = function(e){
    document.querySelectorAll(".modal").forEach((modal) => {
        if (e.target === modal){
            modal.classList.remove("active");
        }
    });
};

setTimeout(() => {
    document.querySelectorAll(".flash").forEach((f) => {
        f.style.transition = "opacity .5s";
        f.style.opacity = "0";
        setTimeout(() => f.remove(), 500);
    });
}, 3000);

function mostrarFlash(mensaje, tipo = "error"){
    const div = document.createElement("div");
    div.className = `flash ${tipo}`;
    div.textContent = mensaje;
    document.body.appendChild(div);

    setTimeout(() => {
        div.style.transition = "opacity .5s";
        div.style.opacity = "0";
        setTimeout(() => div.remove(), 500);
    }, 3000);
}

document.addEventListener("DOMContentLoaded", async () => {
    const selectProducto = document.getElementById("filtroProducto");
    const selectCiudad = document.getElementById("filtroCiudad");
    const selectZona = document.getElementById("filtroZona");

    if (!selectProducto || !selectCiudad || !selectZona){
        return;
    }

    try{
        const productos = await fetch("/api/productos").then((r) => r.json());
        productos.forEach((p) => {
            const option = document.createElement("option");
            option.value = p.id;
            option.textContent = p.nombre;
            selectProducto.appendChild(option);
        });

        const filtros = await fetch("/api/filtros").then((r) => r.json());
        filtros.ciudades.forEach((c) => {
            const option = document.createElement("option");
            option.value = c;
            option.textContent = c;
            selectCiudad.appendChild(option);
        });

        filtros.zonas.forEach((z) => {
            const option = document.createElement("option");
            option.value = z;
            option.textContent = z;
            selectZona.appendChild(option);
        });
    }catch(error){
        mostrarFlash("Error cargando filtros del sistema", "error");
        console.error(error);
    }
});

async function buscarPrecios(){
    const producto = document.getElementById("filtroProducto").value;
    const ciudad = document.getElementById("filtroCiudad").value;
    const zona = document.getElementById("filtroZona").value;

    const url = `/api/comparar-precios?producto=${encodeURIComponent(producto)}&ciudad=${encodeURIComponent(ciudad)}&zona=${encodeURIComponent(zona)}`;

    const contenedor = document.getElementById("resultadoComparacion");
    contenedor.innerHTML = "Buscando...";

    try{
        const respuesta = await fetch(url);
        const datos = await respuesta.json();
        contenedor.innerHTML = "";

        if (datos.error){
            mostrarFlash(datos.error, "error");
            return;
        }

        if (datos.length === 0){
            mostrarFlash("No se encontraron resultados", "error");
            return;
        }

        datos.forEach((d) => {
            contenedor.innerHTML += `
                <div style="padding:10px;border-bottom:1px solid #ddd;">
                    <strong>${d.producto}</strong><br>
                    ${d.tienda} - ${d.sucursal}<br>
                    ${d.ciudad} / ${d.zona}<br>
                    <strong>$${d.precio}</strong>
                </div>
            `;
        });
    }catch(error){
        contenedor.innerHTML = "";
        mostrarFlash("Error al conectar con el servidor", "error");
        console.error(error);
    }
}

function formatearMoneda(valor){
    const numero = Number(valor || 0);
    return numero.toLocaleString("es-MX", {style:"currency", currency:"MXN"});
}

function renderPreview(datos){
    const preview = document.getElementById("apiPreview");
    const resumen = document.getElementById("apiResumen");

    if (!preview || !resumen){
        return;
    }

    if (!datos || datos.length === 0){
        resumen.textContent = "No llegaron productos de APIs externas.";
        preview.innerHTML = "";
        return;
    }

    resumen.textContent = `Productos consultados: ${datos.length}`;

    const filas = datos.map((item) => `
        <tr>
            <td>${item.fuente}</td>
            <td>${item.nombre}</td>
            <td>${item.descripcion || "-"}</td>
            <td>${formatearMoneda(item.precio)}</td>
        </tr>
    `).join("");

    preview.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Fuente</th>
                    <th>Producto</th>
                    <th>Descripcion</th>
                    <th>Precio</th>
                </tr>
            </thead>
            <tbody>${filas}</tbody>
        </table>
    `;
}

async function consumirApisExternas(){
    const preview = document.getElementById("apiPreview");
    const resumen = document.getElementById("apiResumen");

    if (preview){
        preview.innerHTML = "Consultando APIs externas...";
    }
    if (resumen){
        resumen.textContent = "";
    }

    try{
        const response = await fetch("/api/preview-precios");
        const data = await response.json();

        if (!response.ok || data.error){
            throw new Error(data.error || "No se pudo consumir las APIs.");
        }

        renderPreview(data.productos || []);
        mostrarFlash("Datos externos cargados correctamente", "success");
    }catch(error){
        if (preview){
            preview.innerHTML = "";
        }
        mostrarFlash(error.message || "Error al consumir APIs externas", "error");
        console.error(error);
    }
}

async function sincronizarPreciosExternos(){
    if (!confirm("Se insertaran o actualizaran precios en la BD. Deseas continuar?")){
        return;
    }

    try{
        const response = await fetch("/api/sync-precios", {method:"POST"});
        const data = await response.json();

        if (!response.ok || data.error){
            throw new Error(data.error || "No se pudo sincronizar.");
        }

        const mensaje = [
            `Sincronizacion completada.`,
            `Productos nuevos: ${data.productos_nuevos || 0}`,
            `Productos actualizados: ${data.productos_actualizados || 0}`,
            `Precios insertados: ${data.precios_insertados || 0}`,
            `Precios actualizados: ${data.precios_actualizados || 0}`
        ].join("\n");

        alert(mensaje);
        mostrarFlash("Base de datos sincronizada", "success");
        location.reload();
    }catch(error){
        mostrarFlash(error.message || "Error al sincronizar", "error");
        console.error(error);
    }
}

async function probarExportacion(){
    const endpoint = document.getElementById("exportEndpoint");
    const format = document.getElementById("exportFormat");
    const output = document.getElementById("exportOutput");
    const meta = document.getElementById("exportMeta");

    if (!endpoint || !format || !output || !meta){
        return;
    }

    // URL corregida sin la paginación vieja
    const url = `${endpoint.value}?format=${encodeURIComponent(format.value)}`;
    output.textContent = "Consultando endpoint...";
    meta.textContent = "Ejecutando prueba...";

    try{
        const response = await fetch(url);
        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        const rawText = await response.text();

        let body = rawText;
        if (contentType.includes("application/json")){
            try{
                body = JSON.stringify(JSON.parse(rawText), null, 2);
            }catch(_e){
                body = rawText;
            }
        }

        output.textContent = body;
        
        // Enlace clickeable verde agregado
        meta.innerHTML = `URL: <a href="${url}" target="_blank" style="color: #a8d5c4; text-decoration: underline;">${url}</a> | Status: ${response.status} | Fecha: ${new Date().toLocaleString("es-MX")}`;

        if (!response.ok){
            mostrarFlash(`Respuesta HTTP ${response.status}`, "error");
        }else{
            mostrarFlash("Prueba de exportacion completada", "success");
        }
    }catch(error){
        output.textContent = "";
        meta.textContent = "Error al ejecutar prueba.";
        mostrarFlash("No se pudo consumir el endpoint de exportacion", "error");
        console.error(error);
    }
}

// Nueva funcion para pegar JSON
async function pegarJsonApi() {
    const inputTexto = prompt("Pega aquí tu código JSON estructurado del producto:");
    
    if (!inputTexto) return;

    try {
        const datosJson = JSON.parse(inputTexto);

        const response = await fetch("/api/importar_json", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(datosJson)
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || "Error en el servidor.");
        }

        mostrarFlash(data.mensaje, "success");
        
    } catch (error) {
        mostrarFlash("Error: Asegúrate de que el JSON esté bien escrito y use comillas dobles.", "error");
        console.error(error);
    }
}