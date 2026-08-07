
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

    generateBtn.addEventListener("click", async function () {

        const architectureFile = document.getElementById("architectureImage").files[0];
        const requirementFile = document.getElementById("requirementDocument").files[0];
        const githubUrl = document.getElementById("githubUrl").value.trim();
        const codeSnippet = document.getElementById("codeSnippet").value.trim();

        let errors = [];

        if (!architectureFile) {
            errors.push("Please upload the Architecture Image.");
        }

        if (!requirementFile) {
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

         // Disable button and change text
        generateBtn.disabled = true;
        generateBtn.innerHTML = "Generating Documentation...";

        try {

            const response = await fetch("/api/github/repository/files", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    repo_url: githubUrl,
                    // branch: "master",
                    max_files: 20
                })
            });

            const githubData = await response.json();

            console.log("GitHub Response:", githubData);

            if (!response.ok) {
                alert(githubData.detail || "GitHub API Failed");
                return;
            }

            // alert("Repository fetched successfully.");

            const formData = new FormData();
            formData.append("architectureImage", architectureFile);
            formData.append("requirementDocument", requirementFile);
            formData.append("codeSnippet", codeSnippet);
            // githubFiles is a string because backend expects Form(...)
            formData.append(
                "githubFiles",
                JSON.stringify(githubData.files)
            );



            const generateResponse = await fetch("/api/generate-documentation", {
                method: "POST",
                body: formData
            });

            if (!generateResponse.ok) {
                alert("Documentation generation failed.");
                return;
            }

            const blob = await generateResponse.blob();

            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "TestingDocumentation.pdf";
            a.click();
            URL.revokeObjectURL(url);

            setTimeout(() => {
                window.location.reload();
            }, 1000);

        }
        catch (err) {
            console.error(err);
            alert("Something went wrong.");
        } finally {
            // Restore button
            generateBtn.disabled = false;
            generateBtn.innerHTML = "Generate Documentation";
        }

    });


});
