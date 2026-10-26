set terminal pngcairo size 2400,1600 font 'DejaVu Sans,22' # Render with native Gnuplot and Cairo.
set output 'training_curves.png' # Save the reproducible training figure.
set datafile separator ',' # Read unchanged Origin-compatible tables.
set multiplot layout 2,1 title 'Archived friction operator training | original mesh' # Mark the historical mesh scope.
set grid # Add readable reference lines.
set xlabel 'Completed epoch' # Use actual completed epochs.
set ylabel 'Validation group relative error (%)' # Convert recorded dimensionless ratios to percent.
plot 'weights/initial/seed_17/curve.csv' using 1:($4*100) with lines lw 3 title 'Initial seed 17', 'weights/initial/seed_41/curve.csv' using 1:($4*100) with lines lw 3 title 'Initial seed 41' # Plot recorded validation errors only.
set xlabel 'Completed continuation epoch (round 2)' # Identify the separate continuation stage.
plot 'weights/active/round_2/seed_17/curve.csv' using 1:($4*100) with lines lw 3 title 'Active seed 17', 'weights/active/round_2/seed_41/curve.csv' using 1:($4*100) with lines lw 3 title 'Active seed 41', 'weights/random/round_2/seed_41/curve.csv' using 1:($4*100) with lines lw 3 title 'Random seed 41' # Keep compared histories in their proper stage.
unset multiplot # Close the native rendered page.
