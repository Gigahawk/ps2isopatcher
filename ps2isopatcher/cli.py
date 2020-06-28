from ps2isopatcher.iso import Ps2Iso


def main():
    f_name = "mm.iso"
    iso = Ps2Iso(f_name)
    print(iso.pvd.l_path_table)
    for dir in iso.path_tables.l_path_table.get_paths():
        print(dir)


if __name__ == "__main__":
    main()


