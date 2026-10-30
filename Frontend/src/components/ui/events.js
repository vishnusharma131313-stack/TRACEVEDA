/* Global document-level interactions. */
document.addEventListener("click",(event)=>{

    const dropdown =
        document.querySelector(".role-dropdown");

    if(
        dropdown &&
        !dropdown.contains(event.target)
    ){

        document
        .getElementById("roleMenu")
        .classList.remove("open");

    }

});
