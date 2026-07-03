const searchField = document.querySelector("#searchField");

const tableOutput = document.querySelector(".table-output");
const appTable = document.querySelector(".app-table");
const paginationContainer = document.querySelector(".pagination-container");
tableOutput.style.display = "none";
const noResults = document.querySelector(".no-results");
const tbody = document.querySelector(".table-body");

searchField.addEventListener("keyup", (e) => {
  const searchValue = e.target.value;

  if (searchValue.trim().length > 0) {
    paginationContainer.style.display = "none";
    tbody.innerHTML = "";
    fetch("/income/search-income", {
      body: JSON.stringify({ searchText: searchValue }),
      method: "POST",
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("data", data);
        appTable.style.display = "none";
        tableOutput.style.display = "block";

        if (data.length === 0) {
          noResults.style.display = "block";
          tableOutput.style.display = "none";
        } else {
          noResults.style.display = "none";
          data.forEach((item) => {
            tbody.innerHTML += `
                <tr class="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td class="px-6 py-4 tabular-nums">${item.amount}</td>
                    <td class="px-6 py-4">${item.source}</td>
                    <td class="px-6 py-4 text-muted">${item.description}</td>
                    <td class="px-6 py-4">${item.date}</td>
                    <td class="px-6 py-4 text-right">
                        <a href="/income/edit-income/${item.id}" class="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white px-4 py-1.5 rounded text-xs font-medium transition-colors">Edit</a>
                    </td>
                </tr>`;
          });
        }
      });
  } else {
    tableOutput.style.display = "none";
    appTable.style.display = "block";
    paginationContainer.style.display = "flex";
  }
});
