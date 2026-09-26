library(dplyr)

folder = "Simplified Hackathon Dataset V3/ImputedPopulationsC1/"
files = list.files(folder, full.names = T)

parents = tibble()
tot_genomic = list()

for(fi in files){
  print(fi)
  fam_i = str_extract(fi, "(?<=C1/).*(?=_Imp)")
  gen_i = read.csv(fi, row.names = 1)
  p1i = rownames(gen_i)[1]
  p2i = rownames(gen_i)[2]
  
  tot_genomic[[fam_i]] = gen_i
  
  parents = bind_rows(parents, data.frame(fam_i, p1=p1i, p2=p2i))
}

# save(tot_genomic, file = "script_R/tot_genomic.RData")

phenotype_c1 <- read.csv("Simplified Hackathon Dataset V3/C1_Phenotype_Data_V2.csv")
parents = phenotype_c1 |> 
  distinct(shorthand_x, YEAR_x) |> 
  right_join(x = _, y = parents, c("shorthand_x" = "fam_i"))


attach(parents)
parents$n1 = 0
parents$n2 = 0
for(i in seq(nrow(parents))){
  parents$n1[i] = sum((p1[i] == p1) + (p1[i] == p2))
  parents$n2[i] = sum((p2[i] == p1) + (p2[i] == p2))
  
  y1i = sort(unique(YEAR_x[(p1[i] == p1) | (p1[i] == p2)]))
  y2i = sort(unique(YEAR_x[(p2[i] == p1) | (p2[i] == p2)]))
  parents$tot_y1[i] = paste(y1i, collapse = ",")
  parents$tot_y2[i] = paste(y2i, collapse = ",")
}
detach(parents)

parents$p1[!(parents$p1 %in% parents$p2)]
parents$p2[!(parents$p2 %in% parents$p1)]


# write.csv(parents, "script_R/parents.csv", row.names = F)

