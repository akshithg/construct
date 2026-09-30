/* ###
 * Export the controller step function as decompiled C.
 * @category Export
 */

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.FileWriter;
import java.io.PrintWriter;

public class ExportController extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException("expected one output path argument");
        }

        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException(decompiler.getLastMessage());
        }

        try (PrintWriter writer = new PrintWriter(new FileWriter(args[0]))) {
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            boolean found = false;
            while (functions.hasNext() && !monitor.isCancelled()) {
                Function function = functions.next();
                if (!function.getName().endsWith("fmi_do_step")) {
                    continue;
                }
                DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                if (!result.decompileCompleted()) {
                    throw new IllegalStateException(result.getErrorMessage());
                }
                writer.println(result.getDecompiledFunction().getC());
                found = true;
            }
            if (!found) {
                throw new IllegalStateException("fmi_do_step export was not found");
            }
        } finally {
            decompiler.dispose();
        }
    }
}
