from seleniumbase import BaseCase


class MyTourClass(BaseCase):
    def test_google_maps_tour(self):
        self.open("https://www.google.com/maps/@42.3591234,-71.0915634,15z")
        self.wait_for_element("#searchboxinput", timeout=20)
        self.wait_for_element("#minimap", timeout=20)
        self.wait_for_element("#zoom", timeout=20)

        self.create_tour(theme="introjs")
        self.add_tour_step(
            "Welcome to Google Maps!", title="✅ SeleniumBase Tours 🌎"
        )
        self.add_tour_step(
            "Type in a location here.", "#searchboxinput", title="Search Box"
        )
        self.add_tour_step(
            "Then click here to show it on the map.",
            "#searchbox-searchbutton",
            alignment="bottom",
        )
        self.add_tour_step(
            "Or click here to get driving directions.",
            "#searchbox-directions",
            alignment="bottom",
        )
        self.add_tour_step(
            "Use this button to switch to Satellite view.",
            "div.widget-minimap-shim",
            alignment="right",
        )
        self.add_tour_step(
            "Click here to zoom in.", "#widget-zoom-in", alignment="left"
        )
        self.add_tour_step(
            "Or click here to zoom out.", "#widget-zoom-out", alignment="left"
        )
        self.add_tour_step(
            "Use the Menu button to see more options.",
            ".searchbox-hamburger-container",
            alignment="right",
        )
        self.add_tour_step(
            "Or click here to see more Google apps.",
            '[title="Google apps"]',
            alignment="left",
        )
        self.add_tour_step(
            "Thanks for using SeleniumBase Tours!",
            title="🚃 End of Guided Tour 🚃",
        )
        self.export_tour(filename="maps_introjs_tour.js")
        self.play_tour()
