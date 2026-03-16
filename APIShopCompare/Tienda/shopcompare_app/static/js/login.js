/* TOGGLE CONTRASEÑA */
const toggle = document.getElementById("togglePassword");
const password = document.getElementById("password");

toggle.addEventListener("click", () => {
    const type = password.getAttribute("type") === "password" ? "text" : "password";
    password.setAttribute("type", type);

    toggle.classList.toggle("fa-eye");
    toggle.classList.toggle("fa-eye-slash");
});

/* SPINNER AL ENVIAR */
const form = document.getElementById("loginForm");
const spinner = document.getElementById("spinner");
const login = document.getElementById("loginBox");
const body = document.body; // referencia al body

form.addEventListener("submit", (e) => {
    e.preventDefault();

    // ocultar login y mostrar spinner
    login.style.display = "none";
    spinner.style.display = "flex";

    // agregar clase para ocultar el botón de regresar
    body.classList.add("loading");

    setTimeout(() => {
        // enviar formulario después de la animación
        form.submit();
    }, 3000);
});

/* MENSAJE ERROR DESDE BACKEND */
function mostrarError(mensaje) {
    const box = document.getElementById("errorBox");

    box.innerText = mensaje;
    box.style.display = "block";

    setTimeout(() => {
        box.style.display = "none";
    }, 3000);
}