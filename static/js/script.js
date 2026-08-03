
    const architectureInput = document.getElementById("architectureImage");
    const architectureName = document.getElementById("architectureFileName");

    architectureInput.addEventListener("change", function () {
        if (this.files.length > 0) {
            architectureName.innerHTML =
                `<i class="fa-solid fa-image"></i> ${this.files[0].name}`;
        }
    });

    const documentInput = document.getElementById("requirementDocument");
    const documentName = document.getElementById("documentFileName");

    documentInput.addEventListener("change", function () {
        if (this.files.length > 0) {
            documentName.innerHTML =
                `<i class="fa-solid fa-file-lines"></i> ${this.files[0].name}`;
        }
    });


    document.addEventListener("DOMContentLoaded", function () {
    const generateBtn = document.getElementById("generateBtn");
    generateBtn.addEventListener("click", function () {
        const architectureImage = document.getElementById("architectureImage").files.length;
        const requirementDocument = document.getElementById("requirementDocument").files.length;
        const githubUrl = document.getElementById("githubUrl").value.trim();
        const codeSnippet = document.getElementById("codeSnippet").value.trim();

        let errors = [];

        if (architectureImage === 0) {
            errors.push("Please upload the Architecture Image.");
        }

        if (requirementDocument === 0) {
            errors.push("Please upload the Requirement Document.");
        }

        if (githubUrl === "") {
            errors.push("Please enter the GitHub Repository URL.");
        }

        if (codeSnippet === "") {
            errors.push("Please enter the Code Snippet.");
        }

        if (errors.length > 0) {
            alert(errors.join("\n"));
            return;
        }

        alert("All inputs are valid. Ready to generate documentation.");

    });

});