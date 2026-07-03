const searchField = document.querySelector("#searchField");
const tableOutput = document.querySelector(".table-output");
const appTable = document.querySelector(".app-table");
const paginationContainer = document.querySelector(".pagination-container");
const noResults = document.querySelector(".no-results");
const tbody = document.querySelector(".table-body"); // We will append card HTML here

// Get currency from data attribute on a container
const container = document.querySelector('[data-currency]');
const currency = container ? container.getAttribute('data-currency') : '';

let debounceTimer;

if (tableOutput) {
  tableOutput.style.display = "none";
}

if (searchField) {
  searchField.addEventListener("keyup", (e) => {
    clearTimeout(debounceTimer);
    
    debounceTimer = setTimeout(() => {
      const searchValue = e.target.value;

      if (searchValue.trim().length > 0) {
        if (paginationContainer) paginationContainer.style.display = "none";
        tbody.innerHTML = "";
        
        fetch("/search-expenses", {
          body: JSON.stringify({ searchText: searchValue }),
          method: "POST",
        })
          .then((res) => res.json())
          .then((data) => {
            if (appTable) appTable.style.display = "none";
            if (tableOutput) tableOutput.style.display = "block";

            if (data.length === 0) {
              if (noResults) noResults.style.display = "block";
              if (tableOutput) tableOutput.style.display = "none";
            } else {
              if (noResults) noResults.style.display = "none";
              
              data.forEach((item) => {
                // Determine Edit URL pattern (assuming /edit-expense/{id})
                // Note: Hardcoding URL pattern as fallback since we can't use Django template tag here
                const editUrl = `/expense-edit/${item.id}`; 
                
                tbody.innerHTML += `
                  <div class="glass-card p-4 hover:bg-white/5 transition-all group flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div class="flex items-center gap-4">
                          <div class="w-10 h-10 rounded-full bg-surface-elevated border border-white/5 flex items-center justify-center text-lg shadow-inner">
                              🏷️
                          </div>
                          <div>
                              <h4 class="font-semibold text-light text-base">${item.description}</h4>
                              <div class="flex items-center gap-2 text-sm text-muted mt-1">
                                  <span class="px-2 py-0.5 rounded text-xs font-medium bg-white/5 border border-white/5">${item.category}</span>
                                  <span>•</span>
                                  <span>${item.date}</span>
                              </div>
                          </div>
                      </div>
                      
                      <div class="flex items-center justify-between sm:justify-end gap-4 sm:w-1/3">
                          <div class="text-right">
                              <span class="font-bold text-danger tabular-nums block">-${currency}${item.amount}</span>
                          </div>
                          <a href="${editUrl}" class="w-8 h-8 rounded flex items-center justify-center text-muted hover:text-primary hover:bg-primary/10 transition-colors opacity-100 sm:opacity-0 group-hover:opacity-100">
                              <i data-lucide="edit-2" class="w-4 h-4"></i>
                          </a>
                      </div>
                  </div>
                `;
              });
              
              // Re-initialize Lucide icons for dynamically added content
              if (typeof lucide !== 'undefined') {
                lucide.createIcons();
              }
            }
          });
      } else {
        if (tableOutput) tableOutput.style.display = "none";
        if (appTable) appTable.style.display = "block";
        if (paginationContainer) paginationContainer.style.display = "flex";
        if (noResults) noResults.style.display = "none";
      }
    }, 200); // 200ms debounce
  });
}
