const searchField = document.querySelector("#searchField");
const tableOutput = document.querySelector(".table-output");
const appTable = document.querySelector(".app-table");
const paginationContainer = document.querySelector(".pagination-container");
const tbody = document.querySelector(".table-body");
const noResults = document.querySelector(".no-results");
const filterPanel = document.querySelector("#filterPanel");

if (searchField) {
  tableOutput.style.display = "none";

  searchField.addEventListener("keyup", (e) => {
    const searchValue = e.target.value;

    if (searchValue.trim().length > 0) {
      paginationContainer.style.display = "none";
      if (filterPanel) filterPanel.style.display = "none";
      tbody.innerHTML = "";
      
      fetch("/investments/search/", {
        body: JSON.stringify({ searchText: searchValue }),
        method: "POST",
      })
        .then((res) => res.json())
        .then((data) => {
          appTable.style.display = "none";
          tableOutput.style.display = "block";

          if (data.length === 0) {
            noResults.style.display = "block";
            tableOutput.style.display = "none";
          } else {
            noResults.style.display = "none";
            
            data.forEach((item) => {
              const pnlColorClass = item.net_pnl > 0 ? 'text-success' : (item.net_pnl < 0 ? 'text-danger' : 'text-muted');
              const statusHtml = item.status === 'Active' 
                ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-success/10 text-success border border-success/20">Active</span>`
                : `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted/10 text-muted border border-muted/20">Sold</span>`;

              tbody.innerHTML += `
                <tr class="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td class="px-6 py-4">
                    <span class="font-medium text-light">${item.name}</span>
                  </td>
                  <td class="px-6 py-4 text-muted">${item.investment_type}</td>
                  <td class="px-6 py-4 tabular-nums text-muted">${item.amount_invested}</td>
                  <td class="px-6 py-4 tabular-nums text-muted">${item.returns}</td>
                  <td class="px-6 py-4 tabular-nums font-medium ${pnlColorClass}">
                    ${parseFloat(item.net_pnl).toFixed(2)}
                  </td>
                  <td class="px-6 py-4">
                    ${statusHtml}
                  </td>
                  <td class="px-6 py-4 text-muted">${item.date}</td>
                  <td class="px-6 py-4 text-right">
                    <div class="flex justify-end gap-2">
                      <a href="/investments/edit/${item.id}/" class="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white px-3 py-1.5 rounded text-xs font-medium transition-colors">Edit</a>
                      <form action="/investments/delete/${item.id}/" method="post" class="inline" onsubmit="return confirm('Are you sure you want to delete this investment?');">
                        <button type="submit" class="bg-danger/10 hover:bg-danger/20 text-danger border border-danger/20 px-3 py-1.5 rounded text-xs font-medium transition-colors">Delete</button>
                      </form>
                    </div>
                  </td>
                </tr>`;
            });
          }
        });
    } else {
      tableOutput.style.display = "none";
      appTable.style.display = "block";
      paginationContainer.style.display = "flex";
      noResults.style.display = "none";
      if (filterPanel && filterPanel.classList.contains("hidden") === false) {
          // If it was supposed to be shown, we keep it hidden if we want, or display it. 
          // The index.html toggles classes, so if it doesn't have 'hidden', display block.
          filterPanel.style.display = "block"; 
      }
    }
  });
}
